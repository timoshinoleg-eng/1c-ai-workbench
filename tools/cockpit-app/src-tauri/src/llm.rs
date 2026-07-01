//! OpenAI-compatible chat client used by the Cockpit chat tab.
//!
//! Minimal, blocking-friendly HTTP wrapper around the `/chat/completions`
//! endpoint. Tool calling is implemented as a synchronous loop: the model
//! can ask to call a tool, the cockpit invokes the tool against the running
//! MCP servers, the result is fed back to the model, and the loop continues
//! until the model returns a plain text answer.
//!
//! The wrapper is intentionally small. Streaming is not supported in v0.2.0
//! because the UI is a simple input/output panel; clients receive the whole
//! final answer at once.

use std::time::Duration;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::config::LlmConfig;
use crate::mcp::McpManager;

/// A single chat message that goes into the request `messages` array.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tool_call_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tool_calls: Option<Value>,
}

/// One entry in the chat response history returned to the UI.
/// A turn can be either a final text answer or a tool call record.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ChatTurn {
    pub role: String,
    pub content: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tool_name: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tool_result: Option<String>,
}

/// The full result of a single chat request from the UI's perspective.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ChatResponse {
    pub final_text: String,
    pub turns: Vec<ChatTurn>,
    pub model: String,
}

/// The role played in the system prompt. Russian/English. The actual text
/// gets translated at the i18n layer; this module just sends a string.
pub const SYSTEM_PROMPT_RU: &str = "\
Ты — локальный AI-ассистент для работы с выгрузкой конфигурации 1С:Предприятие. \
Отвечай простыми словами. Называй конкретные файлы, объекты метаданных и \
строки кода, которые нашёл через инструменты. Если готового ответа нет — \
честно скажи. После ответа укажи, как пользователь может проверить ответ \
руками. Не выдумывай факты, которых нет в выгрузке. \
\
Используй инструменты (1c-code-index, 1c-skills, 1c-prompt-gallery, \
1c-help-index) для поиска файлов, символов, справки и метаданных.";

const REQUEST_TIMEOUT: Duration = Duration::from_secs(120);
const MAX_TOOL_ROUNDS: usize = 5;

#[derive(Debug, Serialize)]
struct OpenAiRequest<'a> {
    model: &'a str,
    messages: Vec<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tools: Option<Vec<Value>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_choice: Option<&'static str>,
    temperature: f32,
}

#[derive(Debug, Deserialize)]
struct OpenAiResponse {
    #[serde(default)]
    choices: Vec<OpenAiChoice>,
    #[serde(default)]
    model: Option<String>,
}

#[derive(Debug, Deserialize)]
struct OpenAiChoice {
    message: OpenAiAssistantMessage,
}

#[derive(Debug, Deserialize)]
struct OpenAiAssistantMessage {
    #[serde(default)]
    content: Option<String>,
    #[serde(default)]
    tool_calls: Option<Vec<OpenAiToolCall>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct OpenAiToolCall {
    id: String,
    #[serde(default)]
    function: Option<OpenAiFunction>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct OpenAiFunction {
    name: String,
    #[serde(default)]
    arguments: Option<String>,
}

pub fn build_system_prompt(dump_path: &str) -> String {
    format!("{SYSTEM_PROMPT_RU}\n\nПуть к выгрузке: {dump_path}")
}

pub async fn chat(
    llm: &LlmConfig,
    dump_path: &str,
    user_messages: Vec<ChatMessage>,
    mcp: &McpManager,
) -> Result<ChatResponse, String> {
    if llm.api_key.trim().is_empty() {
        return Err(
            "API key is not configured. Open Settings → AI и введите API key.".to_string(),
        );
    }

    let client = reqwest::Client::builder()
        .timeout(REQUEST_TIMEOUT)
        .build()
        .map_err(|e| format!("http client: {e}"))?;

    let tools = build_tool_definitions(mcp);
    let system = build_system_prompt(dump_path);
    let mut messages: Vec<Value> = Vec::with_capacity(user_messages.len() + 1);
    messages.push(json!({"role": "system", "content": system}));
    for m in &user_messages {
        messages.push(serde_json::to_value(m).map_err(|e| format!("encode message: {e}"))?);
    }

    let mut turns: Vec<ChatTurn> = Vec::new();
    let mut final_text = String::new();
    let mut model = llm.model.clone();

    for _round in 0..MAX_TOOL_ROUNDS {
        let req = OpenAiRequest {
            model: &llm.model,
            messages: messages.clone(),
            tools: if tools.is_empty() { None } else { Some(tools.clone()) },
            tool_choice: if tools.is_empty() { None } else { Some("auto") },
            temperature: 0.2,
        };

        let url = format!("{}/chat/completions", llm.base_url.trim_end_matches('/'));
        let resp = client
            .post(&url)
            .bearer_auth(&llm.api_key)
            .json(&req)
            .send()
            .await
            .map_err(|e| format!("request: {e}"))?;

        let status = resp.status();
        let body_text = resp
            .text()
            .await
            .map_err(|e| format!("read body: {e}"))?;
        if !status.is_success() {
            return Err(format!("LLM API error {status}: {}", truncate(&body_text, 500)));
        }

        let parsed: OpenAiResponse = serde_json::from_str(&body_text)
            .map_err(|e| format!("decode response: {e}; body={}", truncate(&body_text, 200)))?;
        if let Some(m) = &parsed.model {
            model = m.clone();
        }
        let choice = parsed
            .choices
            .first()
            .ok_or_else(|| "no choices in response".to_string())?;

        let tool_calls = choice.message.tool_calls.clone().unwrap_or_default();
        if tool_calls.is_empty() {
            final_text = choice.message.content.clone().unwrap_or_default();
            turns.push(ChatTurn {
                role: "assistant".into(),
                content: final_text.clone(),
                tool_name: None,
                tool_result: None,
            });
            break;
        }

        // Persist the assistant's tool-call message verbatim so the model
        // sees its own decision on the next round.
        let mut assistant_msg = json!({"role": "assistant"});
        if let Some(c) = &choice.message.content {
            assistant_msg["content"] = json!(c);
        }
        assistant_msg["tool_calls"] = json!(tool_calls);
        messages.push(assistant_msg);

        for tc in tool_calls {
            let Some(func) = tc.function else {
                continue;
            };
            let args: Value = func
                .arguments
                .as_deref()
                .and_then(|s| serde_json::from_str(s).ok())
                .unwrap_or_else(|| json!({}));
            let (server, tool, result_text) =
                dispatch_tool(mcp, &func.name, args).await.unwrap_or_else(|e| {
                    (
                        "<unknown>".to_string(),
                        func.name.clone(),
                        format!("error: {e}"),
                    )
                });
            turns.push(ChatTurn {
                role: "tool".into(),
                content: String::new(),
                tool_name: Some(format!("{server}.{tool}")),
                tool_result: Some(result_text.clone()),
            });
            messages.push(json!({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_text,
            }));
        }
    }

    if final_text.is_empty() {
        // We exhausted the tool-calling loop without a plain text answer.
        // Push a synthetic final turn so the UI can show "no answer" cleanly.
        final_text =
            "Модель не вернула текстовый ответ после серии вызовов инструментов.".to_string();
        turns.push(ChatTurn {
            role: "assistant".into(),
            content: final_text.clone(),
            tool_name: None,
            tool_result: None,
        });
    }

    Ok(ChatResponse {
        final_text,
        turns,
        model,
    })
}

/// Build the tool list for the model. Each entry maps an MCP tool name
/// ("server.tool") to a thin adapter that we can call from this module.
fn build_tool_definitions(mcp: &McpManager) -> Vec<Value> {
    mcp.list()
        .iter()
        .filter(|s| s.enabled)
        .flat_map(|s| {
            // We expose the tool surface as a curated subset: a small set
            // of well-known tools the LLM can pick from. We do not list
            // every MCP tool dynamically (some servers expose dozens and
            // the model picks poorly). A future revision can list all.
            let candidates: &[(&str, &str, Value)] = &[
                (
                    "search_code",
                    "1c-code-index",
                    json!({
                        "type": "function",
                        "function": {
                            "name": "search_code",
                            "description": "Full-text search across the indexed BSL and XML dump.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "Search query."},
                                    "limit": {"type": "integer", "description": "Max results (default 10)."}
                                },
                                "required": ["query"]
                            }
                        }
                    }),
                ),
                (
                    "find_symbol",
                    "1c-code-index",
                    json!({
                        "type": "function",
                        "function": {
                            "name": "find_symbol",
                            "description": "Find a BSL symbol (function, procedure, variable) by exact name.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Symbol name."}
                                },
                                "required": ["name"]
                            }
                        }
                    }),
                ),
                (
                    "get_function_context",
                    "1c-code-index",
                    json!({
                        "type": "function",
                        "function": {
                            "name": "get_function_context",
                            "description": "Get the full source of a function or procedure by name.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Function name."}
                                },
                                "required": ["name"]
                            }
                        }
                    }),
                ),
                (
                    "search_1c_help",
                    "1c-help-index",
                    json!({
                        "type": "function",
                        "function": {
                            "name": "search_1c_help",
                            "description": "Search the local 1C help (.hbk) index.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "Help search query."},
                                    "limit": {"type": "integer", "description": "Max results."}
                                },
                                "required": ["query"]
                            }
                        }
                    }),
                ),
                (
                    "cf_info",
                    "1c-skills",
                    json!({
                        "type": "function",
                        "function": {
                            "name": "cf_info",
                            "description": "Read metadata about the configuration (objects, forms, modules).",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "object_name": {"type": "string", "description": "Optional object name filter."}
                                }
                            }
                        }
                    }),
                ),
            ];
            candidates
                .iter()
                .filter(|(name, srv, _)| *srv == s.name && mcp_has_tool(mcp, &s.name, name))
                .map(|(_, _, def)| def.clone())
                .collect::<Vec<_>>()
        })
        .collect()
}

fn mcp_has_tool(mcp: &McpManager, server: &str, tool: &str) -> bool {
    // McpManager does not currently expose a list-tools API; we assume the
    // common well-known tools are present. A dynamic check is a future
    // improvement. For v0.2.0 the curated list above is the source of truth.
    let _ = (mcp, server, tool);
    true
}

async fn dispatch_tool(
    mcp: &McpManager,
    tool: &str,
    args: Value,
) -> Result<(String, String, String), String> {
    let (server, inner) = match tool {
        "search_code" => ("1c-code-index", tool),
        "find_symbol" => ("1c-code-index", tool),
        "get_function_context" => ("1c-code-index", tool),
        "search_1c_help" => ("1c-help-index", tool),
        "cf_info" => ("1c-skills", tool),
        // Allow the LLM to call by "server.tool" form, e.g. "1c-code-index.find_symbol".
        composite => {
            if let Some((s, t)) = composite.split_once('.') {
                (s, t)
            } else {
                return Err(format!("unknown tool: {composite}"));
            }
        }
    };
    let started = std::time::Instant::now();
    let raw = mcp.call_tool(server, inner, args).await?;
    let text = serde_json::to_string_pretty(&raw).unwrap_or_else(|_| raw.to_string());
    let _ = started;
    Ok((server.to_string(), inner.to_string(), truncate(&text, 8000)))
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max {
        s.to_string()
    } else {
        let mut end = max;
        while !s.is_char_boundary(end) {
            end -= 1;
        }
        format!("{}…(truncated)", &s[..end])
    }
}

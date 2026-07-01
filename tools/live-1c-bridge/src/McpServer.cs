using System.Text;
using System.Text.Json;
using Live1CBridge.Models;

namespace Live1CBridge;

public sealed class McpServer
{
    private readonly PipeBridge _pipe;
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web) { WriteIndented = false };

    public McpServer(PipeBridge pipe) => _pipe = pipe;

    public async Task RunAsync(CancellationToken cancellationToken)
    {
        var stdin = Console.OpenStandardInput();
        var stdout = Console.OpenStandardOutput();
        while (!cancellationToken.IsCancellationRequested)
        {
            JsonRpcRequest request;
            try { request = await ReadMcpFrameAsync(stdin, cancellationToken); }
            catch (EndOfStreamException) { break; }

            var response = await HandleAsync(request, cancellationToken);
            if (response is not null) await WriteMcpFrameAsync(stdout, response, cancellationToken);
        }
    }

    private async Task<JsonRpcResponse?> HandleAsync(JsonRpcRequest request, CancellationToken cancellationToken)
    {
        try
        {
            return request.Method switch
            {
                "initialize" => Result(request, new
                {
                    protocolVersion = "2024-11-05",
                    capabilities = new { tools = new { } },
                    serverInfo = new { name = "live-1c-bridge", version = "0.1.0" }
                }),
                "notifications/initialized" => null,
                "tools/list" => Result(request, new { tools = ToolCatalog.All }),
                "tools/call" => Result(request, await CallToolAsync(request.Params, cancellationToken)),
                _ => Error(request, -32601, $"Unknown method: {request.Method}")
            };
        }
        catch (Exception ex)
        {
            return Error(request, -32603, ex.Message, ex.GetType().FullName);
        }
    }

    private async Task<object> CallToolAsync(JsonElement? parameters, CancellationToken cancellationToken)
    {
        if (parameters is null) throw new ArgumentException("Missing params");
        var root = parameters.Value;
        var name = root.GetProperty("name").GetString() ?? throw new ArgumentException("Tool name is required");
        var args = root.TryGetProperty("arguments", out var arguments) ? arguments : JsonSerializer.SerializeToElement(new { }, JsonOptions);
        var result = await _pipe.SendAsync(name, args, cancellationToken);
        return new
        {
            content = new[] { new { type = "text", text = JsonSerializer.Serialize(result, JsonOptions) } },
            isError = !result.Success
        };
    }

    private static JsonRpcResponse Result(JsonRpcRequest request, object result) => new("2.0", request.Id, result);
    private static JsonRpcResponse Error(JsonRpcRequest request, int code, string message, object? data = null) => new("2.0", request.Id, null, new JsonRpcError(code, message, data));

    private static async Task<JsonRpcRequest> ReadMcpFrameAsync(Stream stream, CancellationToken cancellationToken)
    {
        var headerBytes = new List<byte>();
        var buffer = new byte[1];
        while (true)
        {
            var read = await stream.ReadAsync(buffer, cancellationToken);
            if (read == 0) throw new EndOfStreamException();
            headerBytes.Add(buffer[0]);
            if (headerBytes.Count >= 4 && headerBytes[^4] == '\r' && headerBytes[^3] == '\n' && headerBytes[^2] == '\r' && headerBytes[^1] == '\n') break;
        }
        var header = Encoding.ASCII.GetString(headerBytes.ToArray());
        var lengthLine = header.Split("\r\n", StringSplitOptions.RemoveEmptyEntries).FirstOrDefault(x => x.StartsWith("Content-Length:", StringComparison.OrdinalIgnoreCase));
        if (lengthLine is null || !int.TryParse(lengthLine.Split(':', 2)[1].Trim(), out var length)) throw new InvalidDataException("Invalid MCP Content-Length");
        var body = new byte[length];
        var offset = 0;
        while (offset < length)
        {
            var read = await stream.ReadAsync(body.AsMemory(offset, length - offset), cancellationToken);
            if (read == 0) throw new EndOfStreamException();
            offset += read;
        }
        return JsonSerializer.Deserialize<JsonRpcRequest>(body, JsonOptions) ?? throw new InvalidDataException("Invalid JSON-RPC request");
    }

    private static async Task WriteMcpFrameAsync<T>(Stream stream, T payload, CancellationToken cancellationToken)
    {
        var body = JsonSerializer.SerializeToUtf8Bytes(payload, JsonOptions);
        var header = Encoding.ASCII.GetBytes($"Content-Length: {body.Length}\r\n\r\n");
        await stream.WriteAsync(header, cancellationToken);
        await stream.WriteAsync(body, cancellationToken);
        await stream.FlushAsync(cancellationToken);
    }
}

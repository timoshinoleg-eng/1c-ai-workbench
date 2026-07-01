using System.Text.Json;
using System.Text.Json.Serialization;

namespace Live1CBridge.Models;

public sealed record PipeMessage(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("method")] string Method,
    [property: JsonPropertyName("params")] JsonElement Params,
    [property: JsonPropertyName("token")] string? Token = null);

public sealed record PipeResponse(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("result")] MethodResult? Result,
    [property: JsonPropertyName("error")] MethodError? Error = null);

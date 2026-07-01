using System.Text.Json.Serialization;

namespace Live1CBridge.Models;

public sealed record MethodResult(
    [property: JsonPropertyName("success")] bool Success,
    [property: JsonPropertyName("value")] object? Value = null,
    [property: JsonPropertyName("type")] string? Type = null,
    [property: JsonPropertyName("metadata")] IReadOnlyDictionary<string, object?>? Metadata = null)
{
    public static MethodResult Ok(object? value = null, string? type = null, IReadOnlyDictionary<string, object?>? metadata = null) => new(true, value, type, metadata);
    public static MethodResult Fail(string message, string? code = null) => new(false, null, "error", new Dictionary<string, object?> { ["message"] = message, ["code"] = code });
}

public sealed record MethodError(
    [property: JsonPropertyName("code")] string Code,
    [property: JsonPropertyName("message")] string Message,
    [property: JsonPropertyName("details")] object? Details = null);

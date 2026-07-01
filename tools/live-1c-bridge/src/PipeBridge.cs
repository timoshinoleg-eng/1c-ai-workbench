using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using Live1CBridge.Models;

namespace Live1CBridge;

public sealed class PipeBridge
{
    private readonly string _pipeName;
    private readonly int _timeoutMs;
    private readonly string? _token;
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    public PipeBridge(string pipeName, int timeoutMs, string? token)
    {
        _pipeName = pipeName;
        _timeoutMs = timeoutMs;
        _token = token;
    }

    public async Task<MethodResult> SendAsync(string method, object? parameters, CancellationToken cancellationToken)
    {
        await using var pipe = new NamedPipeClientStream(".", _pipeName, PipeDirection.InOut, PipeOptions.Asynchronous);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(_timeoutMs);
        await pipe.ConnectAsync(_timeoutMs, timeout.Token);

        var id = Guid.NewGuid().ToString("N");
        var json = JsonSerializer.SerializeToElement(parameters ?? new { }, JsonOptions);
        var request = new PipeMessage(id, method, json, _token);
        await WriteFrameAsync(pipe, request, timeout.Token);
        var response = await ReadFrameAsync<PipeResponse>(pipe, timeout.Token);
        if (response.Error is not null)
        {
            return MethodResult.Fail(response.Error.Message, response.Error.Code);
        }

        return response.Result ?? MethodResult.Fail("Empty pipe response", "empty_response");
    }

    public static async Task WriteFrameAsync<T>(Stream stream, T payload, CancellationToken cancellationToken)
    {
        var body = JsonSerializer.SerializeToUtf8Bytes(payload, JsonOptions);
        var header = Encoding.ASCII.GetBytes($"Content-Length: {body.Length}\r\n\r\n");
        await stream.WriteAsync(header, cancellationToken);
        await stream.WriteAsync(body, cancellationToken);
        await stream.FlushAsync(cancellationToken);
    }

    public static async Task<T> ReadFrameAsync<T>(Stream stream, CancellationToken cancellationToken)
    {
        var headerBytes = new List<byte>();
        var buffer = new byte[1];
        while (true)
        {
            var read = await stream.ReadAsync(buffer, cancellationToken);
            if (read == 0) throw new EndOfStreamException("Pipe closed before header");
            headerBytes.Add(buffer[0]);
            if (headerBytes.Count >= 4 && headerBytes[^4] == '\r' && headerBytes[^3] == '\n' && headerBytes[^2] == '\r' && headerBytes[^1] == '\n') break;
        }

        var header = Encoding.ASCII.GetString(headerBytes.ToArray());
        var lengthLine = header.Split("\r\n", StringSplitOptions.RemoveEmptyEntries).FirstOrDefault(x => x.StartsWith("Content-Length:", StringComparison.OrdinalIgnoreCase));
        if (lengthLine is null || !int.TryParse(lengthLine.Split(':', 2)[1].Trim(), out var length)) throw new InvalidDataException("Invalid Content-Length header");

        var body = new byte[length];
        var offset = 0;
        while (offset < length)
        {
            var read = await stream.ReadAsync(body.AsMemory(offset, length - offset), cancellationToken);
            if (read == 0) throw new EndOfStreamException("Pipe closed before body");
            offset += read;
        }

        return JsonSerializer.Deserialize<T>(body, JsonOptions) ?? throw new InvalidDataException("Invalid JSON frame");
    }
}

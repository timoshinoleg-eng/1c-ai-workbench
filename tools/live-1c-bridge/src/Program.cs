using Live1CBridge;

var options = CliOptions.Parse(args);
using var cts = new CancellationTokenSource();
Console.CancelKeyPress += (_, eventArgs) => { eventArgs.Cancel = true; cts.Cancel(); };

if (options.Mode == "host")
{
    Console.Error.WriteLine($"live-1c-bridge host starting pipe={options.PipeName}");
    var host = new PipeHost(options.PipeName, options.Token, options.AllowUnsafeExec);
    if (!string.IsNullOrWhiteSpace(options.ConnectionString))
    {
        var result = host.Connect(options.ConnectionString, options.ProgId);
        Console.Error.WriteLine($"connect: {result.Success}");
        if (!result.Success) Console.Error.WriteLine(result.Metadata?["message"]);
    }
    await host.RunAsync(cts.Token);
    return;
}

if (options.Mode == "mcp")
{
    var pipe = new PipeBridge(options.PipeName, options.PipeTimeoutMs, options.Token);
    await new McpServer(pipe).RunAsync(cts.Token);
    return;
}

PrintUsage();

static void PrintUsage()
{
    Console.Error.WriteLine("live-1c-bridge --mode mcp|host --pipe-name NAME --pipe-token TOKEN [--connection-string str] [--prog-id V83.COMConnector] [--allow-unsafe-exec]");
    Console.Error.WriteLine("Unsafe eval requires both --allow-unsafe-exec and LIVE_1C_BRIDGE_UNSAFE=1.");
    Console.Error.WriteLine("SECURITY: --pipe-token is REQUIRED for host mode. The bridge is a privileged channel");
    Console.Error.WriteLine("into the operator's 1C infobase; the host refuses to start without a non-empty token.");
    Console.Error.WriteLine("The named pipe DACL is also restricted to current user + local Administrators.");
}

internal sealed class CliOptions
{
    public string Mode { get; init; } = "mcp";
    public string PipeName { get; init; } = "1c-com-bridge";
    public int PipeTimeoutMs { get; init; } = 30000;
    public string? Token { get; init; }
    public string? ConnectionString { get; init; }
    public string? ProgId { get; init; }
    public bool AllowUnsafeExec { get; init; }

    public static CliOptions Parse(string[] args)
    {
        var values = new Dictionary<string, string?>(StringComparer.OrdinalIgnoreCase);
        var flags = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        for (var i = 0; i < args.Length; i++)
        {
            var arg = args[i];
            if (!arg.StartsWith("--", StringComparison.Ordinal)) continue;
            var key = arg[2..];
            if (key is "allow-unsafe-exec") { flags.Add(key); continue; }
            if (i + 1 >= args.Length) throw new ArgumentException($"Missing value for {arg}");
            values[key] = args[++i];
        }

        var unsafeEnvEnabled = string.Equals(
            Environment.GetEnvironmentVariable("LIVE_1C_BRIDGE_UNSAFE"),
            "1",
            StringComparison.Ordinal
        );

        return new CliOptions
        {
            Mode = values.GetValueOrDefault("mode") ?? "mcp",
            PipeName = values.GetValueOrDefault("pipe-name") ?? "1c-com-bridge",
            PipeTimeoutMs = int.TryParse(values.GetValueOrDefault("pipe-timeout"), out var timeout) ? timeout : 30000,
            Token = values.GetValueOrDefault("pipe-token") ?? Environment.GetEnvironmentVariable("LIVE_1C_BRIDGE_TOKEN"),
            ConnectionString = values.GetValueOrDefault("connection-string") ?? Environment.GetEnvironmentVariable("LIVE_1C_CONNECTION_STRING"),
            ProgId = values.GetValueOrDefault("prog-id"),
            AllowUnsafeExec = flags.Contains("allow-unsafe-exec") && unsafeEnvEnabled
        };
    }
}

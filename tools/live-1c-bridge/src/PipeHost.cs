using System.IO.Pipes;
using System.IO.Pipes.AccessControl;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text.Json;
using Live1CBridge.Models;

namespace Live1CBridge;

public sealed class PipeHost
{
    private readonly string _pipeName;
    private readonly string _token;
    private readonly bool _allowUnsafeExec;
    private readonly ComSession _session = new();
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    public PipeHost(string pipeName, string? token, bool allowUnsafeExec)
    {
        if (string.IsNullOrEmpty(token))
        {
            // Refuse to start without a token: an empty token combined with
            // the default pipe ACL exposes the bridge to every local user.
            // (sec-fix-2026-06-23)
            throw new ArgumentException(
                "A non-empty --pipe-token is required. The bridge is a privileged " +
                "channel into the operator's 1C infobase; an empty token leaves the " +
                "named pipe open to any local process.",
                nameof(token));
        }
        _pipeName = pipeName;
        _token = token;
        _allowUnsafeExec = allowUnsafeExec;
    }

    public MethodResult Connect(string connectionString, string? progId) => _session.Connect(connectionString, progId);

    public async Task RunAsync(CancellationToken cancellationToken)
    {
        var pipeSecurity = BuildRestrictivePipeSecurity();
        while (!cancellationToken.IsCancellationRequested)
        {
            await using var pipe = NamedPipeServerStreamAcl.Create(
                _pipeName,
                PipeDirection.InOut,
                1,
                PipeTransmissionMode.Byte,
                PipeOptions.Asynchronous,
                inBufferSize: 0,
                outBufferSize: 0,
                pipeSecurity);
            await pipe.WaitForConnectionAsync(cancellationToken);
            try
            {
                var request = await PipeBridge.ReadFrameAsync<PipeMessage>(pipe, cancellationToken);
                var response = Handle(request);
                await PipeBridge.WriteFrameAsync(pipe, response, cancellationToken);
            }
            catch (Exception ex)
            {
                var response = new PipeResponse("unknown", null, new MethodError("host_exception", ex.Message, ex.GetType().FullName));
                await PipeBridge.WriteFrameAsync(pipe, response, cancellationToken);
            }
        }
    }

    private static PipeSecurity BuildRestrictivePipeSecurity()
    {
        // Restrict the named pipe DACL to: current user, local Administrators.
        // The DACL is marked protected (no inheritance) and contains only the
        // explicit allow rules below; we do NOT add a Deny-Everyone ACE
        // because every user (including the current user and Administrators)
        // is a member of Everyone, and an explicit Deny ACE for Everyone
        // would block the intended clients. (sec-fix-2026-06-23)
        var security = new PipeSecurity();
        var currentUser = WindowsIdentity.GetCurrent().User
            ?? throw new InvalidOperationException("Cannot resolve current WindowsIdentity.User");
        security.AddAccessRule(new PipeAccessRule(currentUser, PipeAccessRights.ReadWrite | PipeAccessRights.CreateNewInstance, AccessControlType.Allow));
        var admins = new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null);
        security.AddAccessRule(new PipeAccessRule(admins, PipeAccessRights.ReadWrite | PipeAccessRights.CreateNewInstance, AccessControlType.Allow));
        // isProtected=true: ignore inherited ACEs from the parent (process
        // token's default DACL, which usually grants the Users group access).
        // preserveInheritance=false: discard any inherited rules entirely.
        security.SetAccessRuleProtection(isProtected: true, preserveInheritance: false);
        return security;
    }

    // The DACL approach above was revised after the first version used a
    // Deny-Everyone ACE, which inadvertently blocked the intended clients
    // (current user and Administrators are themselves members of Everyone).
    // See SECURITY.md "Known limitations of v1.1.0" for the audit trail.

    private PipeResponse Handle(PipeMessage request)
    {
        if (!string.IsNullOrEmpty(_token) && request.Token != _token)
        {
            return new PipeResponse(request.Id, null, new MethodError("unauthorized", "Invalid pipe token"));
        }

        try
        {
            var result = request.Method switch
            {
                "connect" => _session.Connect(GetString(request.Params, "connectionString", true)!, GetString(request.Params, "progId", false)),
                "get_connection_info" => _session.GetConnectionInfo(),
                "run_query" => _session.RunQuery(GetString(request.Params, "query", true)!, GetParameters(request.Params), GetInt(request.Params, "limit", 100)),
                "get_metadata" => _session.GetMetadata(GetInt(request.Params, "maxObjects", 500)),
                "find_object" => _session.FindObject(GetString(request.Params, "objectType", true)!, GetString(request.Params, "name", true)!, GetString(request.Params, "code", false), GetString(request.Params, "description", false)),
                "get_object_data" => _session.GetObjectData(GetString(request.Params, "objectType", true)!, GetString(request.Params, "name", true)!, GetString(request.Params, "code", false), GetString(request.Params, "description", false)),
                "exec_code" => _session.ExecCode(GetString(request.Params, "code", true)!, _allowUnsafeExec),
                _ => MethodResult.Fail("Unknown method: " + request.Method, "unknown_method")
            };
            return new PipeResponse(request.Id, result);
        }
        catch (Exception ex)
        {
            return new PipeResponse(request.Id, null, new MethodError("method_exception", ex.Message, ex.GetType().FullName));
        }
    }

    private static string? GetString(JsonElement root, string name, bool required)
    {
        if (root.TryGetProperty(name, out var value) && value.ValueKind != JsonValueKind.Null) return value.GetString();
        if (required) throw new ArgumentException(name + " is required");
        return null;
    }

    private static int GetInt(JsonElement root, string name, int fallback)
    {
        return root.TryGetProperty(name, out var value) && value.TryGetInt32(out var result) ? result : fallback;
    }

    private static Dictionary<string, object?>? GetParameters(JsonElement root)
    {
        if (!root.TryGetProperty("parameters", out var value) || value.ValueKind is JsonValueKind.Null or JsonValueKind.Undefined) return null;
        return JsonSerializer.Deserialize<Dictionary<string, object?>>(value.GetRawText(), JsonOptions);
    }
}

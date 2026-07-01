using System.Collections;
using System.Reflection;
using System.Text.Json;
using Microsoft.VisualBasic.CompilerServices;
using Live1CBridge.Models;

namespace Live1CBridge;

public sealed class ComSession
{
    private dynamic? _connection;
    private string? _connectionString;

    public bool IsConnected => _connection is not null;

    public MethodResult Connect(string connectionString, string? progId = null)
    {
        if (string.IsNullOrWhiteSpace(connectionString)) return MethodResult.Fail("connectionString is required", "bad_request");
        var tried = new List<string>();
        foreach (var candidate in BuildProgIds(progId))
        {
            tried.Add(candidate);
            var type = Type.GetTypeFromProgID(candidate);
            if (type is null) continue;
            dynamic connector = Activator.CreateInstance(type)!;
            _connection = connector.Connect(connectionString);
            _connectionString = connectionString;
            return MethodResult.Ok(new { connected = true, progId = candidate }, "connection_info");
        }
        return MethodResult.Fail("1C COMConnector ProgID not found: " + string.Join(", ", tried), "com_connector_not_found");
    }

    public MethodResult GetConnectionInfo()
    {
        return MethodResult.Ok(new { connected = IsConnected, connectionString = RedactConnectionString(_connectionString) }, "connection_info");
    }

    public MethodResult RunQuery(string query, Dictionary<string, object?>? parameters = null, int limit = 100)
    {
        var connection = RequireConnection();
        dynamic q = TryInvoke(connection, "NewObject", "Query", query) ?? TryInvoke(connection, "NewObject", "Запрос", query) ?? throw new InvalidOperationException("Cannot create 1C Query object");
        if (parameters is not null)
        {
            foreach (var pair in parameters) TryInvoke(q, "SetParameter", pair.Key, pair.Value, "УстановитьПараметр");
        }
        dynamic executed = TryInvoke(q, "Execute", null, null, "Выполнить") ?? throw new InvalidOperationException("Query execution failed");
        dynamic result = TryInvoke(executed, "Unload", null, null, "Выгрузить") ?? executed;
        return MethodResult.Ok(TableToRows(result, limit), "table", new Dictionary<string, object?> { ["limit"] = limit });
    }

    public MethodResult GetMetadata(int maxObjects = 500)
    {
        var connection = RequireConnection();
        var result = new List<object?>();
        dynamic metadata = TryGetMember(connection, "Metadata", "Метаданные") ?? throw new InvalidOperationException("Metadata is unavailable");
        TryAddMetadataGroup(result, TryGetMember(metadata, "Catalogs", "Справочники"), "Catalog", maxObjects);
        TryAddMetadataGroup(result, TryGetMember(metadata, "Documents", "Документы"), "Document", maxObjects);
        TryAddMetadataGroup(result, TryGetMember(metadata, "InformationRegisters", "РегистрыСведений"), "InformationRegister", maxObjects);
        TryAddMetadataGroup(result, TryGetMember(metadata, "AccumulationRegisters", "РегистрыНакопления"), "AccumulationRegister", maxObjects);
        TryAddMetadataGroup(result, TryGetMember(metadata, "Constants", "Константы"), "Constant", maxObjects);
        TryAddMetadataGroup(result, TryGetMember(metadata, "Enums", "Перечисления"), "Enum", maxObjects);
        return MethodResult.Ok(result.Take(maxObjects).ToArray(), "metadata_tree", new Dictionary<string, object?> { ["maxObjects"] = maxObjects });
    }

    public MethodResult FindObject(string objectType, string name, string? code = null, string? description = null)
    {
        var connection = RequireConnection();
        dynamic manager = GetObjectManager(connection, objectType, name);
        dynamic? reference = null;
        if (!string.IsNullOrWhiteSpace(code)) reference = TryInvoke(manager, "FindByCode", code, null, "НайтиПоКоду");
        if (reference is null && !string.IsNullOrWhiteSpace(description)) reference = TryInvoke(manager, "FindByDescription", description, null, "НайтиПоНаименованию");
        if (reference is null) return MethodResult.Fail("Object not found", "not_found");
        return MethodResult.Ok(ComValueToJsonValue(reference), "reference");
    }

    public MethodResult GetObjectData(string objectType, string name, string? code = null, string? description = null)
    {
        var found = FindObject(objectType, name, code, description);
        if (!found.Success) return found;
        var connection = RequireConnection();
        dynamic manager = GetObjectManager(connection, objectType, name);
        dynamic? reference = !string.IsNullOrWhiteSpace(code)
            ? TryInvoke(manager, "FindByCode", code, null, "НайтиПоКоду")
            : TryInvoke(manager, "FindByDescription", description, null, "НайтиПоНаименованию");
        if (reference is null) return MethodResult.Fail("Object not found", "not_found");
        dynamic obj = TryInvoke(reference, "GetObject", null, null, "ПолучитьОбъект") ?? throw new InvalidOperationException("Cannot load object data");
        return MethodResult.Ok(ComValueToJsonValue(obj), "object");
    }

    public MethodResult ExecCode(string code, bool allowUnsafeExec)
    {
        if (!allowUnsafeExec) return MethodResult.Fail("exec_code is disabled. Start host with --allow-unsafe-exec.", "unsafe_disabled");
        var connection = RequireConnection();
        dynamic result = TryInvoke(connection, "Eval", code, null, "Вычислить") ?? throw new InvalidOperationException("Eval failed");
        return MethodResult.Ok(ComValueToJsonValue(result), "eval_result");
    }

    private dynamic RequireConnection() => _connection ?? throw new InvalidOperationException("Not connected. Call connect first or start host with --connection-string.");

    private static IEnumerable<string> BuildProgIds(string? preferred)
    {
        if (!string.IsNullOrWhiteSpace(preferred)) yield return preferred;
        yield return "V83.COMConnector";
        yield return "V82.COMConnector";
        yield return "V81.COMConnector";
    }

    private static string? RedactConnectionString(string? value)
    {
        if (value is null) return null;
        return System.Text.RegularExpressions.Regex.Replace(value, "(?i)(Pwd|Password)=[^;]*", "$1=***");
    }

    private static dynamic GetObjectManager(dynamic connection, string objectType, string name)
    {
        dynamic collection = objectType.ToLowerInvariant() switch
        {
            "catalog" or "справочник" => TryGetMember(connection, "Catalogs", "Справочники"),
            "document" or "документ" => TryGetMember(connection, "Documents", "Документы"),
            "informationregister" or "регистрсведений" => TryGetMember(connection, "InformationRegisters", "РегистрыСведений"),
            "accumulationregister" or "регистрнакопления" => TryGetMember(connection, "AccumulationRegisters", "РегистрыНакопления"),
            _ => throw new ArgumentOutOfRangeException(nameof(objectType), $"Unsupported objectType: {objectType}")
        } ?? throw new InvalidOperationException($"1C object collection is unavailable: {objectType}");
        return TryGetIndexed(collection, name) ?? throw new InvalidOperationException($"1C object manager not found: {objectType}.{name}");
    }

    private static void TryAddMetadataGroup(List<object?> result, object? group, string type, int maxObjects)
    {
        try
        {
            foreach (dynamic item in group)
            {
                if (result.Count >= maxObjects) return;
                result.Add(new { type, name = SafeString(() => item.Name), synonym = SafeString(() => item.Synonym), fullName = SafeString(() => item.FullName()) });
            }
        }
        catch { }
    }

    private static IReadOnlyList<object?> TableToRows(dynamic table, int limit)
    {
        var rows = new List<object?>();
        var columns = new List<string>();
        try
        {
            foreach (dynamic col in table.Columns) columns.Add(Convert.ToString(col.Name) ?? "Column");
            foreach (dynamic row in table)
            {
                if (rows.Count >= limit) break;
                var dict = new Dictionary<string, object?>();
                foreach (var column in columns) dict[column] = ComValueToJsonValue(row[column]);
                rows.Add(dict);
            }
        }
        catch
        {
            rows.Add(ComValueToJsonValue(table));
        }
        return rows;
    }

    private static object? ComValueToJsonValue(object? value, int depth = 0)
    {
        if (value is null || depth > 2) return value?.ToString();
        if (value is string or bool or int or long or double or decimal or DateTime) return value;
        if (value is JsonElement) return value;
        if (value is IEnumerable enumerable && value is not string)
        {
            var list = new List<object?>();
            foreach (var item in enumerable)
            {
                if (list.Count >= 100) break;
                list.Add(ComValueToJsonValue(item, depth + 1));
            }
            return list;
        }

        var dict = new Dictionary<string, object?> { ["presentation"] = value.ToString(), ["comType"] = value.GetType().FullName };
        foreach (var property in value.GetType().GetProperties(BindingFlags.Public | BindingFlags.Instance).Take(30))
        {
            try { dict[property.Name] = ComValueToJsonValue(property.GetValue(value), depth + 1); } catch { }
        }
        return dict;
    }

    private static object? TryGetMember(object target, params string[] names)
    {
        foreach (var name in names)
        {
            try { return NewLateBinding.LateGet(target, null, name, Array.Empty<object>(), null, null, null); } catch { }
        }
        return null;
    }

    private static object? TryGetIndexed(object target, string key)
    {
        try { return NewLateBinding.LateIndexGet(target, new object[] { key }, null); } catch { return null; }
    }

    private static object? TryInvoke(object target, string englishName, object? arg1 = null, object? arg2 = null, string? russianName = null)
    {
        var args = new List<object?>();
        if (arg1 is not null) args.Add(arg1);
        if (arg2 is not null) args.Add(arg2);
        foreach (var name in new[] { englishName, russianName }.Where(x => !string.IsNullOrWhiteSpace(x)))
        {
            try { return NewLateBinding.LateGet(target, null, name!, args.ToArray(), null, null, null); } catch { }
        }
        return null;
    }

    private static string? SafeString(Func<object?> getter)
    {
        try { return Convert.ToString(getter()); } catch { return null; }
    }
}

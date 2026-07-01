namespace Live1CBridge;

public static class ToolCatalog
{
    public static readonly object[] All =
    {
        Tool("connect", "Connect host to 1C via COMConnector.", new Dictionary<string, object> { ["connectionString"] = Schema.String(), ["progId"] = Schema.String() }, "connectionString"),
        Tool("get_connection_info", "Return live bridge connection status with secrets redacted.", new Dictionary<string, object>()),
        Tool("run_query", "Run 1C query and return rows.", new Dictionary<string, object> { ["query"] = Schema.String(), ["parameters"] = Schema.Object(), ["limit"] = Schema.Integer() }, "query"),
        Tool("get_metadata", "Return top-level 1C metadata objects.", new Dictionary<string, object> { ["maxObjects"] = Schema.Integer() }),
        Tool("find_object", "Find catalog/document/register object by code or description.", new Dictionary<string, object> { ["objectType"] = Schema.String(), ["name"] = Schema.String(), ["code"] = Schema.String(), ["description"] = Schema.String() }, "objectType", "name"),
        Tool("get_object_data", "Read object attributes/table-parts best-effort through COM.", new Dictionary<string, object> { ["objectType"] = Schema.String(), ["name"] = Schema.String(), ["code"] = Schema.String(), ["description"] = Schema.String() }, "objectType", "name"),
        Tool("exec_code", "Unsafe expression evaluation. Requires host --allow-unsafe-exec.", new Dictionary<string, object> { ["code"] = Schema.String() }, "code")
    };

    private static object Tool(string name, string description, Dictionary<string, object> properties, params string[] required) => new
    {
        name,
        description,
        inputSchema = new { type = "object", properties, required, additionalProperties = false }
    };

    private static class Schema
    {
        public static object String() => new { type = "string" };
        public static object Integer() => new { type = "integer" };
        public static object Object() => new { type = "object" };
    }
}

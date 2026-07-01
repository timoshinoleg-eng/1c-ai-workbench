# Golden demo answers — summary

Demo configuration: `Автосервис` from `IgorKilipenko/onec-auto-repair-shop`.
Index: `C:\1c-ai-workbench\generated\index\source-mirror\.code-index\index.db`.

## 0. Index baseline

- Files: 336
- Functions/procedures: 396
- Classes/objects extracted by generic index: 84
- Calls: 1664
- Text files: 137

## 1. Register movements: accumulation register `Продажи`

**Conclusion:** movements for register `Продажи` are in document `Реализация`, object module.

**Evidence:**

- File: `Documents/Реализация/Ext/ObjectModule.bsl`
- Procedures found by body grep:
  - `записатьДвиженияДокумента`, lines 28–37, match line 30
  - `выполнитьДвижениеПродажиОборот`, lines 192–200, match line 193
- Search command:

```powershell
.\tools\code-index-mcp\target\release\bsl-indexer.exe grep-body --path "C:\1c-ai-workbench\generated\index\source-mirror" --pattern "Движения.Продажи" --language bsl --limit 20
```

**Manual verification:** open document `Реализация` in Configurator/EDT, open object module, find `Движения.Продажи`, verify register writers and procedure flow.

**Confidence:** high — exact BSL body match.

## 2. Form handlers: document `ЗаказНаряд`

**Conclusion:** document form `ЗаказНаряд.ФормаДокумента` has client handlers for service rows and sum recalculation.

**Evidence:**

- File: `Documents/ЗаказНаряд/Forms/ФормаДокумента/Ext/Form/Module.bsl`
- Functions/procedures extracted:
  - `УслугиКоличествоПриИзменении`, lines 3–7
  - `УслугиНоменклатураПриИзменении`, lines 9–31
  - `УслугиПослеУдаления`, lines 33–36
  - `обновитьСуммуПоТекущейСтрокеУслуг`, lines 42–46
  - `обновитьСуммуДокумента`, lines 48–57
- Form XML exists at `Documents/ЗаказНаряд/Forms/ФормаДокумента/Ext/Form.xml`.

**Manual verification:** open document `ЗаказНаряд`, form `ФормаДокумента`, inspect events of table part/service controls, then open form module and find the listed procedures.

**Confidence:** high — indexed module summary contains exact procedures and line ranges.

## 3. Price/sum logic in `ЗаказНаряд`

**Conclusion:** price is filled when service nomenclature changes; row sum is `Цена * Количество`; document sum aggregates row sums.

**Evidence:**

- File: `Documents/ЗаказНаряд/Forms/ФормаДокумента/Ext/Form/Module.bsl`
- `УслугиНоменклатураПриИзменении`, lines 9–31:
  - calls `получитьЦенуНоменклатуры(...)`
  - sets `ткущаяСтрокаУслуг.Цена`
- `обновитьСуммуПоТекущейСтрокеУслуг`, lines 42–46:
  - `ткущаяСтрокаУслуг.Сумма = ткущаяСтрокаУслуг.Цена * ткущаяСтрокаУслуг.Количество`
- `обновитьСуммуДокумента`, lines 48–57:
  - loops over `Объект.Услуги`
  - accumulates `Объект.СуммаДокумента`

**Manual verification:** open `ЗаказНаряд` form module, search for `Цена`, `Количество`, `СуммаДокумента`; change service row in user mode and compare recalculation.

**Confidence:** high — exact indexed procedure bodies.

## 4. Subsystem `Продажи`

**Conclusion:** subsystem `Продажи` exposes sales-related documents, reports and register commands; exact composition should be verified in subsystem XML and command interface.

**Evidence:**

- Files found:
  - `Subsystems/Продажи.xml`
  - `Subsystems/Продажи/Ext/CommandInterface.xml`
  - `Reports/Продажи/Templates/ОсновнаяСхемаКомпоновкиДанных/Ext/Template.xml`
  - `AccumulationRegisters/Продажи.xml`
- Search command:

```powershell
.\tools\code-index-mcp\target\release\bsl-indexer.exe search-text "Продажи" --path "C:\1c-ai-workbench\generated\index\source-mirror" --limit 10
```

**Manual verification:** open subsystem `Продажи` in Configurator/EDT, inspect composition and command interface, then open listed documents/registers/reports.

**Confidence:** medium — text evidence is strong, final composition should be read from subsystem XML/tool output in MCP.

## 5. Plan: add attribute to catalog `Номенклатура`

**Conclusion:** start from catalog metadata and its forms; likely affected areas are element form, list/choice forms, price lookup code, reports and documents that use nomenclature.

**Evidence:**

- Metadata/file paths:
  - `Catalogs/Номенклатура.xml`
  - `Catalogs/Номенклатура/Forms/ФормаЭлемента/Ext/Form.xml`
  - `Catalogs/Номенклатура/Forms/ФормаВыбора/Ext/Form.xml`
  - `Catalogs/Номенклатура/Forms/ФормаСписка/Ext/Form.xml`
- Related code references appear in service/price flows, especially document `ЗаказНаряд` form module using nomenclature and prices.

**Suggested implementation plan:**

1. Add attribute `АртикулПоставщика` to catalog `Номенклатура`.
2. Add it to `ФормаЭлемента`; optionally to list/choice forms if users need search/display.
3. Search for `Catalog.Номенклатура` and `Номенклатура` usages in documents/reports.
4. Check price-related flows and reports for whether supplier article should be displayed or exported.
5. Test create/edit item, list search, document selection, reports/printed forms.

**Manual verification:** open catalog `Номенклатура`, forms, and built-in “Find references”; compare with MCP search results.

**Confidence:** medium — plan is source-backed, but business rules must be confirmed by 1C lead.

## Raw evidence

Full CLI output is saved in `demo-answers\golden_answers_cli.md`.

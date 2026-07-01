# Questions for a 1C developer

Use this pack when the goal is not just to find a file, but to понять, где менять код и что может сломаться.

1. В каком модуле находится основная логика расчёта суммы для документа?
2. Какие процедуры вызываются до и после проведения документа?
3. Какие формы и объектные модули нужно проверить, если добавить новое поле в справочник?
4. Где используются `Контрагенты` или `Номенклатура` в найденном сценарии?
5. Какие места выглядят рискованными для доработки и требуют ручной проверки?

Expected behavior:

- answer contains exact file paths from `generated\index\source-mirror`;
- names modules/procedures/functions when found;
- separates exact evidence from assumptions;
- ends with a short manual verification plan.

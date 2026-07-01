export const name = 'Multi-context: routing single test to non-default context';
export const tags = ['multi-context', 'smoke'];
export const context = 'b';
export const timeout = 60000;

export default async function({ getPageState, navigateSection, openCommand, closeForm, assert, step, log }) {

  await step('Active context is b', async () => {
    // Sanity check — ensure we are routed into b's session
    const state = await getPageState();
    assert.ok(Array.isArray(state.sections) && state.sections.length, 'Sections should be visible');
    log('Sections in b: ' + state.sections.map(s => s.name).join(', '));
  });

  await step('Open Контрагенты in context b', async () => {
    await navigateSection('Склад');
    const state = await openCommand('Контрагенты');
    assert.ok(state.form != null, 'List form should open');
    log('Opened in b: ' + state.title);
    await closeForm();
  });
}

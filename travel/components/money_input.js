export default function(component) {
  const {parentElement, data, setStateValue} = component;
  const input = parentElement.querySelector('input');
  const label = parentElement.querySelector('label');
  const help = parentElement.querySelector('.help');
  const error = parentElement.querySelector('.error');
  input.id = component.key + '-amount';
  label.htmlFor = input.id;
  label.textContent = data.label;
  help.textContent = data.help || '';
  help.hidden = !data.help;
  input.placeholder = parentElement.activeElement === input ? '' : (data.placeholder || '0');
  const clean = value => value.replace(/,/g, '').replace(/\s/g, '');
  const valid = value => value === '' || /^\d+(\.\d*)?$/.test(value);
  const format = value => {
    if (!valid(value) || value === '') return value;
    const [whole, fraction] = value.split('.');
    return whole.replace(/^0+(?=\d)/,'').replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (fraction === undefined ? '' : '.' + fraction);
  };
  if (parentElement.activeElement !== input) input.value = format(data.value || '');
  const beginEditing = () => {
    input.placeholder = '';
    if (/^0(?:\.0*)?$/.test(clean(input.value))) {
      input.value = '';
      input.dataset.clearedZero = 'true';
    }
  };
  input.onfocus = beginEditing;
  input.onclick = beginEditing;
  const showError = () => {
    const invalid = !valid(clean(input.value));
    error.hidden = !invalid;
    input.setAttribute('aria-invalid', String(invalid));
    return invalid;
  };
  input.oninput = () => {
    const cursor = input.selectionStart;
    const logical = input.value.slice(0, cursor).replace(/,/g,'').length;
    const raw = clean(input.value);
    if (valid(raw)) {
      input.value = format(raw);
      let position = 0, seen = 0;
      while (position < input.value.length && seen < logical) {
        if (input.value[position] !== ',') seen++;
        position++;
      }
      input.setSelectionRange(position, position);
    }
    showError();
  };
  const commit = () => {
    let raw = clean(input.value);
    if (raw === '' && input.dataset.clearedZero === 'true') raw = '0';
    if (valid(raw)) raw = clean(format(raw));
    input.value = format(raw);
    delete input.dataset.clearedZero;
    showError();
    // 잘못된 입력도 전달해 이전 금액으로 조용히 계산되지 않게 한다.
    if (raw !== data.value) setStateValue('value', raw);
  };
  input.onblur = () => {
    commit();
    input.placeholder = data.placeholder || '0';
  };
  input.onkeydown = event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      commit();
    }
  };
}

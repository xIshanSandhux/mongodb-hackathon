const rows = document.querySelector('#payment-rows');
const filter = document.querySelector('#status-filter');
const modal = document.querySelector('#payment-modal');
const form = document.querySelector('#payment-form');
const toast = document.querySelector('#toast');
let allPayments = [];

const money = (amount, currency = 'USD') => new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);
const dateLabel = value => new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }).format(new Date(value));
const safe = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

async function refresh() {
  const query = filter.value ? `?status=${encodeURIComponent(filter.value)}` : '';
  try {
    const [filtered, all, summary] = await Promise.all([fetch(`/api/payments${query}`), fetch('/api/payments'), fetch('/api/dashboard/summary')]);
    if (!filtered.ok || !all.ok) throw new Error('Could not load payments');
    const data = await filtered.json();
    allPayments = (await all.json()).payments;
    const metrics = await summary.json();
    rows.innerHTML = data.payments.length ? data.payments.map(paymentRow).join('') : '<tr><td colspan="6" class="empty">No payments match this filter.</td></tr>';
    document.querySelector('#volume').textContent = money(allPayments.filter(p => p.status === 'succeeded').reduce((sum, p) => sum + p.amount, 0));
    document.querySelector('#transaction-count').textContent = allPayments.length;
    document.querySelector('#success-count').textContent = allPayments.filter(p => p.status === 'succeeded').length;
    document.querySelector('#attention-count').textContent = allPayments.filter(p => ['processing','failed'].includes(p.status)).length;
    document.querySelector('#settlement-count').textContent = metrics.settlements ?? 0;
    document.querySelector('#dispute-count').textContent = metrics.disputes ?? 0;
    document.querySelector('#result-count').textContent = `${data.count} payment${data.count === 1 ? '' : 's'}`;
  } catch (error) {
    rows.innerHTML = `<tr><td colspan="6" class="empty">${safe(error.message)}. Refresh to try again.</td></tr>`;
  }
}

function paymentRow(payment) {
  const customer = safe(payment.customer_name);
  const method = payment.card_last4 ? `${safe(payment.card_brand || 'Card')} •••• ${safe(payment.card_last4)}` : safe(payment.payment_method.replace('_', ' '));
  const actions = payment.status === 'succeeded' || payment.status === 'partially_refunded' ? `<button class="row-actions refund" data-id="${safe(payment.id)}" title="Refund payment" aria-label="Refund ${customer}">↶</button>` : payment.status === 'processing' && payment.capture_method === 'manual' ? `<button class="row-actions capture" data-id="${safe(payment.id)}" title="Capture payment">✓</button>` : '';
  return `<tr><td><div class="payment-id">${safe(payment.id)}</div><div class="subtext">${safe(payment.order_id)} · ${method}</div></td><td>${customer}<div class="subtext">${safe(payment.vendor)} · ${safe(payment.customer_email)}</div></td><td>${dateLabel(payment.created_at)}</td><td class="amount">${money(payment.amount, payment.currency)}</td><td><span class="badge ${safe(payment.status)}">${safe(payment.status.replace('_',' '))}</span></td><td>${actions}</td></tr>`;
}

function showToast(message) { toast.textContent = message; toast.classList.add('show'); setTimeout(() => toast.classList.remove('show'), 2800); }
filter.addEventListener('change', refresh);
rows.addEventListener('click', async event => {
  const button = event.target.closest('.refund');
  const capture = event.target.closest('.capture');
  if (!button && !capture) return;
  const action = capture ? 'capture' : 'refund';
  const target = capture || button;
  target.disabled = true;
  const response = await fetch(`/api/payments/${encodeURIComponent(target.dataset.id)}/${action}`, { method: 'POST' });
  const result = await response.json();
  if (!response.ok) showToast(result.detail || 'Refund could not be processed.');
  else showToast(action === 'refund' ? 'Payment refunded successfully.' : 'Payment captured successfully.');
  await refresh();
});
document.querySelector('#open-modal').addEventListener('click', () => modal.showModal());
for (const id of ['close-modal','cancel-modal']) document.querySelector(`#${id}`).addEventListener('click', () => modal.close());
form.addEventListener('submit', async event => {
  event.preventDefault();
  const submit = document.querySelector('#submit-payment');
  const errorLine = document.querySelector('#form-error');
  submit.disabled = true;
  errorLine.textContent = '';
  const data = Object.fromEntries(new FormData(form));
  data.amount = Number(data.amount);
  for (const key of ['card_number','card_exp_month','card_exp_year','card_cvc','customer_phone','description']) if (!data[key]) delete data[key];
  for (const key of ['card_exp_month','card_exp_year']) if (data[key]) data[key] = Number(data[key]);
  try {
    const response = await fetch('/api/payments', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
    const result = await response.json();
    if (!response.ok) throw new Error(Array.isArray(result.detail) ? result.detail.map(item => item.msg).join(', ') : result.detail);
    form.reset(); modal.close(); await refresh();
    showToast(result.status === 'failed' ? 'Payment declined by the test processor.' : 'Payment created successfully.');
  } catch (error) { errorLine.textContent = error.message || 'Payment could not be created.'; }
  finally { submit.disabled = false; }
});
refresh();

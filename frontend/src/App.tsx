import { FormEvent, KeyboardEvent, RefObject, useCallback, useEffect, useRef, useState } from 'react';

const PAGE_SIZE = 8;

function useMore(resetKey: string) {
  const [count, setCount] = useState(PAGE_SIZE);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { setCount(PAGE_SIZE); }, [resetKey]);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) setCount(value => value + PAGE_SIZE);
    }, { rootMargin: '160px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, [resetKey, count]);
  return { count, ref };
}

function ListTools({ query, shown, total, pageIds, picked, onQuery, onPicked, onDelete }: {
  query: string; shown: number; total: number; pageIds: string[]; picked: string[];
  onQuery: (value: string) => void; onPicked: (ids: string[]) => void; onDelete: () => void;
}) {
  const allOn = pageIds.length > 0 && pageIds.every(id => picked.includes(id));
  return <div className="list-tools">
    <input className="list-search" placeholder="Search" value={query} onChange={event => onQuery(event.target.value)} />
    <label className="session-pick"><input type="checkbox" checked={allOn} onChange={event => onPicked(event.target.checked ? [...new Set([...picked, ...pageIds])] : picked.filter(id => !pageIds.includes(id)))} />Select all</label>
    <button type="button" className="text-button" disabled={picked.length === 0} onClick={() => { if (window.confirm(`Delete ${picked.length} selected?`)) onDelete(); }}>Delete</button>
    <span className="list-count">{shown} of {total}</span>
  </div>;
}

function ScrollMore({ node, more }: { node: RefObject<HTMLDivElement | null>; more: boolean }) {
  if (!more) return null;
  return <div ref={node} className="list-more" />;
}

type Product = {
  id: number;
  sku: string;
  shop_id: string;
  name: string;
  description: string;
  price_tnd: string | null;
  availability: 'available' | 'sold_out' | 'unknown';
  facts?: { label: string; value: string }[];
};
type Attachment = '' | 'image' | 'voice' | 'video' | 'location';
type Instruction = {
  id: number;
  source_text: string;
  rules: string[];
  may_answer: string[];
  ask_seller: string[];
  removed?: string[];
  added?: string[];
};
type OrderProgress = {
  product_name: string;
  size: string;
  phone: string;
  address: string;
  missing: string[];
};
type DraftResponse = {
  draft: {
    reply_text: string;
    customer_intent: 'social_conversation' | 'shop_question';
    matched_product_ids: number[];
    used_instruction_ids: number[];
    needs_seller: boolean;
    seller_question: string | null;
  };
  model: string;
  latency_ms: number;
  usage: { input_tokens: number; output_tokens: number; total_tokens: number };
  conversation_id: number | null;
  order: OrderProgress | null;
  priority?: boolean;
  flagged?: boolean;
};
const API = import.meta.env.VITE_API_URL ?? '';

function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [message, setMessage] = useState('');
  const [attachment, setAttachment] = useState<Attachment>('');
  const [instructions, setInstructions] = useState<Instruction[]>([]);
  const [instructionText, setInstructionText] = useState('');
  const [draft, setDraft] = useState<DraftResponse | null>(null);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [turns, setTurns] = useState<{ role: string; text: string; pending?: boolean }[]>([]);
  const [order, setOrder] = useState<OrderProgress | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const waitGeneration = useRef(0);
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const [savingInstruction, setSavingInstruction] = useState(false);
  const [error, setError] = useState('');
  const [productForm, setProductForm] = useState({ sku: '', name: '', description: '', price_tnd: '', availability: 'unknown' as Product['availability'] });
  const [showForm, setShowForm] = useState(false);
  const [usage, setUsage] = useState({ input_tokens: 0, output_tokens: 0, total_tokens: 0, estimated_usd: '0.0000' });
  const [draftFacts, setDraftFacts] = useState<{ label: string; value: string }[]>([]);
  const [formHint, setFormHint] = useState('');
  const [deliveryDays, setDeliveryDays] = useState('');
  const [deliveryPrice, setDeliveryPrice] = useState('');
  const [deliveryNote, setDeliveryNote] = useState('');
  const [page, setPage] = useState<'agents' | 'discussions' | 'integrations' | 'database'>('agents');
  const [threads, setThreads] = useState<{ id: number; preview: string; channel?: string }[]>([]);
  const [channelFilter, setChannelFilter] = useState<'test' | 'whatsapp' | 'facebook'>('test');
  const [find, setFind] = useState({ products: '', instructions: '', threads: '' });
  const productsMore = useMore(find.products);
  const instructionsMore = useMore(find.instructions);
  const threadsMore = useMore(find.threads);
  const [picked, setPicked] = useState({ products: [] as string[], instructions: [] as string[], threads: [] as string[] });
  const [openThread, setOpenThread] = useState<{ conversation_id: number; turns: { role: string; text: string }[] } | null>(null);
  const [sellerReply, setSellerReply] = useState('');
  const [alertCount, setAlertCount] = useState(0);
  const [agentOn, setAgentOn] = useState(() => localStorage.getItem('agent-enabled') !== 'off');
  const [agentSaving, setAgentSaving] = useState(false);

  const loadProducts = useCallback(async () => {
    try {
      const response = await fetch(`${API}/api/v1/products`);
      if (!response.ok) throw new Error('Could not load products. Check that the API is running.');
      setProducts(await response.json() as Product[]);
      setError('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not connect to the API.');
    }
  }, []);

  const loadInstructions = useCallback(async () => {
    try {
      const response = await fetch(`${API}/api/v1/instructions`);
      if (!response.ok) throw new Error('Could not load instructions.');
      setInstructions(await response.json() as Instruction[]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load instructions.');
    }
  }, []);

  const loadUsage = useCallback(async () => {
    try {
      const response = await fetch(`${API}/api/v1/usage`);
      if (!response.ok) return;
      setUsage(await response.json());
    } catch { /* usage stays at zero until the API is up */ }
  }, []);

  const loadAlertCount = useCallback(async () => {
    try {
      const response = await fetch(`${API}/api/v1/alerts`);
      if (!response.ok) return;
      const rows = await response.json() as { id: number }[];
      setAlertCount(rows.length);
    } catch { /* badge stays at the last known count */ }
  }, []);

  const loadShop = useCallback(async () => {
    try {
      const response = await fetch(`${API}/api/v1/shop`);
      if (!response.ok) return;
      const body = await response.json() as { delivery_days: number | null; delivery_price_tnd: string | null };
      setDeliveryDays(body.delivery_days == null ? '' : String(body.delivery_days));
      setDeliveryPrice(body.delivery_price_tnd ?? '');
    } catch { /* shop facts stay empty until the API is up */ }
  }, []);

  useEffect(() => {
    void loadProducts(); void loadInstructions(); void loadUsage(); void loadAlertCount(); void loadShop();
    const timer = window.setInterval(() => { void loadUsage(); void loadAlertCount(); }, 4000);
    return () => window.clearInterval(timer);
  }, [loadProducts, loadInstructions, loadUsage, loadAlertCount, loadShop]);
  useEffect(() => {
    if (page !== 'discussions') return;
    void (async () => {
      const response = await fetch(`${API}/api/v1/conversations`);
      if (response.ok) setThreads(await response.json());
    })();
  }, [page]);
  useEffect(() => {
    if (instructions[0] && instructionText === '') setInstructionText(instructions[0].source_text);
  }, [instructions, instructionText]);
  useEffect(() => {
    const thread = threadRef.current;
    if (thread) thread.scrollTop = thread.scrollHeight;
  }, [turns, draft]);

  function productProblems(): string {
    const name = productForm.name.trim();
    if (name.length < 2 || !/[a-zA-Z\u0600-\u06FF]/.test(name)) return 'Enter a real product name, such as Robe d’été.';
    if (productForm.price_tnd.trim() && !/^\d+([.,]\d{1,3})?$/.test(productForm.price_tnd.trim())) return 'Price must be a number in TND, or leave it empty.';
    return '';
  }

  async function saveProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const problem = productProblems();
    if (problem) { setFormHint(problem); return; }
    setBusy(true); setError(''); setFormHint('');
    try {
      const response = await fetch(`${API}/api/v1/products/${encodeURIComponent(productForm.sku)}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: productForm.name, description: productForm.description, price_tnd: productForm.price_tnd || null, availability: productForm.availability, facts: draftFacts.filter(fact => fact.label.trim() && fact.value.trim()) }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      setProductForm({ sku: '', name: '', description: '', price_tnd: '', availability: 'unknown' });
      setDraftFacts([]);
      setShowForm(false); await loadProducts();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Product save failed.'); }
    finally { setBusy(false); }
  }

  function editProduct(product: Product) {
    setProductForm({
      sku: product.sku,
      name: product.name,
      description: product.description,
      price_tnd: product.price_tnd ?? '',
      availability: product.availability,
    });
    setDraftFacts(product.facts ?? []);
    setShowForm(true);
  }

  async function deleteProduct(sku: string) {
    if (!window.confirm('Delete this product?')) return;
    setBusy(true); setError('');
    try {
      const response = await fetch(`${API}/api/v1/products/${encodeURIComponent(sku)}`, { method: 'DELETE' });
      if (!response.ok) throw new Error(await errorMessage(response));
      if (productForm.sku === sku) setShowForm(false);
      await loadProducts();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not delete the product.'); }
    finally { setBusy(false); }
  }

  async function structureProduct() {
    const problem = productProblems();
    const description = productForm.description.trim();
    if (problem) { setFormHint(problem); return; }
    if (description.length < 12) {
      setFormHint('Read description only pulls facts that are written down. “blabla” has none. Write something like “Robe rouge en coton, taille M”.');
      setDraftFacts([]);
      return;
    }
    setBusy(true); setError(''); setFormHint('');
    try {
      const response = await fetch(`${API}/api/v1/products/structure`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: productForm.name || 'Product', description: productForm.description, price_tnd: productForm.price_tnd || null, availability: productForm.availability }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const body = await response.json() as { facts: { label: string; value: string }[] };
      setDraftFacts(body.facts);
      setFormHint(body.facts.length ? 'Check these facts, then save. Nothing is stored until you press Save.' : 'No facts were written in that description. Add color, size, or material, or save the product without facts.');
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not read the description.'); }
    finally { setBusy(false); }
  }

  async function addInstruction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSavingInstruction(true); setError('');
    try {
      const response = await fetch(`${API}/api/v1/instructions`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: instructionText }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const saved = await response.json() as Instruction;
      setInstructions([saved]);
      setInstructionText(saved.source_text);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Instruction save failed.'); }
    finally { setSavingInstruction(false); }
  }

  async function removeInstruction(id: number) {
    if (!window.confirm('Delete this instruction?')) return;
    setBusy(true); setError('');
    try {
      const response = await fetch(`${API}/api/v1/instructions/${id}`, { method: 'DELETE' });
      if (!response.ok && response.status !== 204) throw new Error(await errorMessage(response));
      setInstructionText('');
      setInstructions([]);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not remove the instruction.'); }
    finally { setBusy(false); }
  }

  async function deletePicked(kind: 'products' | 'instructions' | 'threads') {
    const ids = picked[kind];
    if (!ids.length) return;
    setBusy(true); setError('');
    try {
      for (const id of ids) {
        const path = kind === 'products' ? `/api/v1/products/${encodeURIComponent(id)}` : kind === 'instructions' ? `/api/v1/instructions/${id}` : `/api/v1/conversations/${id}`;
        const response = await fetch(`${API}${path}`, { method: 'DELETE' });
        if (!response.ok && response.status !== 204) throw new Error(await errorMessage(response));
        if (kind === 'threads' && conversationId === Number(id)) { setConversationId(null); setTurns([]); }
        if (kind === 'threads' && openThread?.conversation_id === Number(id)) setOpenThread(null);
      }
      setPicked({ ...picked, [kind]: [] });
      if (kind === 'products') await loadProducts();
      if (kind === 'instructions') { setInstructions([]); setInstructionText(''); }
      if (kind === 'threads') { const response = await fetch(`${API}/api/v1/conversations`); if (response.ok) setThreads(await response.json()); }
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not delete the selection.'); }
    finally { setBusy(false); }
  }

  async function createDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError('');
    if (!agentOn) { setError('The agent is off. Turn it on in Integrations.'); return; }
    const sent = message.trim();
    if (!sent && !attachment) return;
    setMessage('');
    setSending(true);
    let hold = false;
    setTurns(current => [
      ...current.filter(turn => !turn.pending),
      ...(sent ? [{ role: 'buyer', text: sent }] : []),
      ...(attachment ? [] : [{ role: 'draft', text: 'Waiting up to 40 seconds for more messages…', pending: true }]),
    ]);
    try {
      const response = await fetch(`${API}/api/v1/replies/draft`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: sent,
          ...(attachment ? { attachment } : {}),
          ...(conversationId ? { conversation_id: conversationId } : {}),
        }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const body = await response.json() as DraftResponse & { waiting?: boolean };
      setDraft(body);
      if (body.conversation_id) setConversationId(body.conversation_id);
      if (body.waiting && body.conversation_id) {
        const watch = ++waitGeneration.current;
        const startedAt = Date.now();
        const conversation = body.conversation_id;
        const poll = async () => {
          if (waitGeneration.current !== watch) return;
          const again = await fetch(`${API}/api/v1/conversations/${conversation}`);
          if (!again.ok || waitGeneration.current !== watch) return;
          const view = await again.json() as { turns: { role: string; text: string }[]; order: OrderProgress | null };
          const last = view.turns[view.turns.length - 1];
          const shown = view.turns.map(turn => ({ role: turn.role === 'buyer' ? 'buyer' : 'draft', text: turn.text }));
          if (last?.role === 'draft') {
            setTurns(shown);
            setOrder(view.order);
            setSending(false);
            return;
          }
          setTurns([...shown, { role: 'draft', text: 'Waiting up to 40 seconds for more messages…', pending: true }]);
          if (Date.now() - startedAt < 180000) window.setTimeout(() => void poll(), 2000);
          else setSending(false);
        };
        hold = true;
        window.setTimeout(() => void poll(), 2000);
        return;
      }
      const saved = body.draft.reply_text || body.draft.seller_question || '';
      setTurns(current => [
        ...current.filter(turn => !turn.pending),
        ...(saved ? [{ role: 'draft', text: saved }] : []),
      ]);
      setOrder(body.order);
    } catch (cause) {
      setTurns(current => current.filter(turn => !turn.pending));
      setError(cause instanceof Error ? cause.message : 'Draft failed.');
    } finally { if (!hold) setSending(false); }
  }

  return <div className="app-shell">
    <header className="topbar">
      <a className="brand" href="#home" aria-label="Souk home"><span className="brand-mark">s</span><span>souq<span className="brand-dot">.</span></span></a>
      <div className="shop-switch"><span className="shop-avatar">D</span><b>Boutique</b></div>
    </header>

    <aside className="sidebar" aria-label="Main navigation">
      <span className="nav-label">WORKSPACE</span>
      <button type="button" className={page === 'agents' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('agents')}>Agents</button>
      <button type="button" className={page === 'discussions' ? 'nav-item active' : 'nav-item'} onClick={() => { setPage('discussions'); setAlertCount(0); void fetch(`${API}/api/v1/alerts/seen`, { method: 'POST' }); }}>Discussions{alertCount > 0 && <span className="nav-badge" aria-label={`${alertCount} alerts`}>{alertCount}</span>}</button>
      <button type="button" className={page === 'integrations' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('integrations')}>Integrations</button>
      <button type="button" className={page === 'database' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('database')}>Database</button>
    </aside>

    <main className="main" id="overview">
      {error && <div className="alert" role="alert"><span>!</span>{error}<button onClick={() => setError('')} aria-label="Dismiss">×</button></div>}

      {page === 'agents' && <section className="usage-bar" aria-label="Usage"><div><span>In</span><b>{usage.input_tokens.toLocaleString()}</b></div><div><span>Out</span><b>{usage.output_tokens.toLocaleString()}</b></div><div><span>Tokens</span><b>{usage.total_tokens.toLocaleString()}</b></div><div><span>Cost</span><b>${usage.estimated_usd}</b></div><div><span>Agent</span><b>{agentOn ? 'On' : 'Off'}</b></div></section>}
      <div className="content-grid">
        {page === 'database' && <section className="panel catalog-panel" id="catalog">
          <form className="product-form" onSubmit={event => { event.preventDefault(); void (async () => { setBusy(true); setError(''); setDeliveryNote(''); const response = await fetch(`${API}/api/v1/shop`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ delivery_days: deliveryDays.trim() ? Number(deliveryDays) : null, delivery_price_tnd: deliveryPrice.trim() || null }) }); if (!response.ok) setError(await errorMessage(response)); else setDeliveryNote('Delivery saved.'); setBusy(false); })(); }}>
            <div className="form-fields">
              <div className="form-row">
                <label>Delivery days<input inputMode="numeric" placeholder="2" value={deliveryDays} onChange={event => { setDeliveryDays(event.target.value); setDeliveryNote(''); }} /></label>
                <label>Delivery price (TND)<input inputMode="decimal" placeholder="7" value={deliveryPrice} onChange={event => { setDeliveryPrice(event.target.value); setDeliveryNote(''); }} /></label>
              </div>
            </div>
            <button className="button primary" disabled={busy}>{busy ? 'Saving…' : 'Save delivery'}</button>
            {deliveryNote && <p className="form-hint" role="status">{deliveryNote}</p>}
          </form>
          <div className="panel-heading"><div><h2>Products <span className="count-badge">{products.length}</span></h2></div><button className="button secondary add-button" onClick={() => setShowForm(!showForm)}><span>＋</span> Add</button></div>
          {showForm && <form className="product-form" onSubmit={saveProduct}>
            <div className="form-header"><strong>Product</strong><button type="button" className="close-button" onClick={() => setShowForm(false)} aria-label="Close">×</button></div>
            <div className="form-fields">
              <div className="form-row">
                <label>Name<input required minLength={2} maxLength={160} placeholder="Robe d’été" value={productForm.name} onChange={e => { const name = e.target.value; setProductForm({ ...productForm, name, sku: name.trim().toLowerCase().replace(/\s+/g, '_') }); }} /></label>
                <label>Price (TND)<input inputMode="decimal" placeholder="65" value={productForm.price_tnd} onChange={e => setProductForm({ ...productForm, price_tnd: e.target.value })} /></label>
              </div>
              <label className="wide">Description<textarea maxLength={2000} rows={3} placeholder="Red cotton robe, size M. Optional. Read description turns details like this into facts." value={productForm.description} onChange={e => setProductForm({ ...productForm, description: e.target.value })} /></label>
              <div className="form-row">
                <label>Availability<select value={productForm.availability} onChange={e => setProductForm({ ...productForm, availability: e.target.value as Product['availability'] })}><option value="unknown">Unknown</option><option value="available">Available</option><option value="sold_out">Sold out</option></select></label>
                <div className="read-description"><button type="button" className="button secondary" disabled={busy || productForm.description.trim().length < 12} onClick={() => void structureProduct()}>Read description</button><small>Optional. Pulls color, size, and material from the text. It does not save the product.</small></div>
              </div>
              {formHint && <p className="form-hint">{formHint}</p>}
              {draftFacts.length > 0 && <div className="fact-table wide">{draftFacts.map((fact, index) => <label key={index}>{fact.label}<input value={fact.value} onChange={event => setDraftFacts(draftFacts.map((item, itemIndex) => itemIndex === index ? { ...item, value: event.target.value } : item))} /></label>)}</div>}
            </div>
            <button className="button primary" disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
          </form>}
          {(() => { const q = find.products.trim().toLowerCase(); const rows = products.filter(product => !q || `${product.name} ${product.sku} ${product.description ?? ''}`.toLowerCase().includes(q)); const shown = rows.slice(0, productsMore.count); return <><ListTools query={find.products} shown={shown.length} total={rows.length} pageIds={shown.map(product => product.sku)} picked={picked.products} onQuery={value => setFind({ ...find, products: value })} onPicked={ids => setPicked({ ...picked, products: ids })} onDelete={() => void deletePicked('products')} />{shown.length ? <div className="product-list">{shown.map(product => <article className="product-row" key={product.id}><label className="session-pick"><input type="checkbox" checked={picked.products.includes(product.sku)} onChange={event => setPicked({ ...picked, products: event.target.checked ? [...picked.products, product.sku] : picked.products.filter(id => id !== product.sku) })} />Select</label><div className="product-thumb">{product.name.slice(0, 1).toUpperCase()}</div><div className="product-info"><strong>{product.name}</strong><span>{product.facts?.length ? product.facts.map(fact => `${fact.label}: ${fact.value}`).join(' · ') : (product.description || product.sku)}</span></div><div className="product-price">{product.price_tnd ? `${product.price_tnd} TND` : ''}<span className={`availability ${product.availability}`}>{product.availability.replace('_', ' ')}</span><span className="product-actions"><button type="button" className="text-button" onClick={() => editProduct(product)}>Edit</button><button type="button" className="text-button" onClick={() => void deleteProduct(product.sku)}>Delete</button></span></div></article>)}</div> : <div className="empty-state"><button className="button primary" onClick={() => setShowForm(true)}>Add product</button></div>}<ScrollMore node={productsMore.ref} more={shown.length < rows.length} /></>; })()}
          <button className="text-button" onClick={() => void loadProducts()}>Refresh</button>
        </section>}

        {page === 'agents' && <section className="panel copilot-panel">
          <div className="panel-heading"><div><h2>Test</h2><p>Try the assistant here. Buyers do not see this.</p></div><button type="button" className="text-button" onClick={() => { setConversationId(null); setTurns([]); setOrder(null); setDraft(null); setMessage(''); }}>New</button></div>
          <div className="thread" ref={threadRef}>{turns.map((turn, index) => <p key={`${turn.role}-${index}`} className={turn.pending ? 'pending-turn' : turn.role === 'buyer' ? 'buyer-turn' : 'draft-turn'}><b>{turn.role === 'buyer' ? 'Buyer' : 'Draft'}</b>{turn.pending ? <span className="reply-loading"><span className="reply-spinner"/>Writing…</span> : turn.text}</p>)}{turns.length === 0 && <p className="thread-empty">No messages</p>}</div>
          {order?.product_name && <div className="order-progress"><span>{order.product_name}{order.size ? ` · ${order.size}` : ''}</span></div>}
          <form onSubmit={createDraft} className="copilot-form"><textarea id="buyer-message" rows={2} maxLength={4000} value={message} onChange={event => setMessage(event.target.value)} onKeyDown={(event: KeyboardEvent<HTMLTextAreaElement>) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.stopPropagation(); event.currentTarget.form?.requestSubmit(); } }} /><div className="send-row"><select id="buyer-attachment" value={attachment} onChange={event => setAttachment(event.target.value as Attachment)}><option value="">No attachment</option><option value="image">Photo</option><option value="voice">Voice</option><option value="video">Video</option><option value="location">Location</option></select><button className="button primary draft-button" type="submit" disabled={sending || !agentOn || (!message.trim() && !attachment)}>{sending ? 'Sending…' : 'Send'}</button></div></form>
        </section>}
        {page === 'agents' && <section className="panel instruction-panel" id="instructions">
          <div className="panel-heading"><h2>Instructions</h2></div>
          <form onSubmit={addInstruction} className="instruction-form">
            <textarea maxLength={4000} rows={6} placeholder="We are closed on Sunday. If a parcel arrives damaged, hand the chat to me." value={instructionText} onChange={event => setInstructionText(event.target.value)} required />
            <button className="button primary" type="submit" disabled={savingInstruction || !instructionText.trim()}>{savingInstruction ? 'Saving…' : 'Save instruction'}</button>
          </form>
          {(() => { const q = find.instructions.trim().toLowerCase(); const rows = instructions.filter(item => !q || item.source_text.toLowerCase().includes(q)); const shown = rows.slice(0, instructionsMore.count); return <><ListTools query={find.instructions} shown={shown.length} total={rows.length} pageIds={shown.map(item => String(item.id))} picked={picked.instructions} onQuery={value => setFind({ ...find, instructions: value })} onPicked={ids => setPicked({ ...picked, instructions: ids })} onDelete={() => void deletePicked('instructions')} />{shown.map(item => <article className="instruction-card" key={item.id}><label className="session-pick"><input type="checkbox" checked={picked.instructions.includes(String(item.id))} onChange={event => setPicked({ ...picked, instructions: event.target.checked ? [...picked.instructions, String(item.id)] : picked.instructions.filter(id => id !== String(item.id)) })} />Select</label>{(item.removed && item.removed.length > 0) || (item.added && item.added.length > 0) ? <div className="diff-block"><p>What changed</p>{item.removed && item.removed.length > 0 && <ul className="diff-removed">{item.removed.map(fact => <li key={fact}>{fact}</li>)}</ul>}{item.added && item.added.length > 0 && <ul className="diff-added">{item.added.map(fact => <li key={fact}>{fact}</li>)}</ul>}</div> : null}<p className="skill-text">{item.source_text}</p><button type="button" className="text-button" onClick={() => void removeInstruction(item.id)}>Remove</button></article>)}<ScrollMore node={instructionsMore.ref} more={shown.length < rows.length} /></>; })()}
        </section>}
        {page === 'discussions' && <section className="panel discussion-panel">
          <div className="panel-heading"><h2>Discussions</h2><div className="channel-filters"><button type="button" className={channelFilter === 'test' ? 'channel-filter active' : 'channel-filter'} onClick={() => setChannelFilter('test')} aria-label="Test">T</button><button type="button" className={channelFilter === 'whatsapp' ? 'channel-filter active' : 'channel-filter'} onClick={() => setChannelFilter('whatsapp')} aria-label="WhatsApp"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a9 9 0 0 0-7.7 13.5L3 21l4.7-1.2A9 9 0 1 0 12 3zm0 2a7 7 0 0 1 0 14c-1.1 0-2.2-.3-3.1-.8l-.3-.2-2.2.6.6-2.1-.2-.3A7 7 0 0 1 12 5z"/></svg></button><button type="button" className={channelFilter === 'facebook' ? 'channel-filter active' : 'channel-filter'} onClick={() => setChannelFilter('facebook')} aria-label="Facebook"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 9h3V6h-3c-2.2 0-4 1.8-4 4v2H8v3h2v7h3v-7h2.6l.4-3H13v-2c0-.6.4-1 1-1z"/></svg></button></div><button type="button" className="text-button" onClick={() => void (async () => { const response = await fetch(`${API}/api/v1/conversations`); if (response.ok) setThreads(await response.json()); })()}>Refresh</button></div>
          <div className="session-list">{channelFilter !== 'test' && <p className="thread-empty">No {channelFilter} discussions yet.</p>}{channelFilter === 'test' && (() => { const q = find.threads.trim().toLowerCase(); const rows = threads.filter(thread => (thread.channel ?? 'test') === 'test' && (!q || `${thread.id} ${thread.preview}`.toLowerCase().includes(q))); const shown = rows.slice(0, threadsMore.count); return <><ListTools query={find.threads} shown={shown.length} total={rows.length} pageIds={shown.map(thread => String(thread.id))} picked={picked.threads} onQuery={value => setFind({ ...find, threads: value })} onPicked={ids => setPicked({ ...picked, threads: ids })} onDelete={() => void deletePicked('threads')} />{shown.length === 0 && <p className="thread-empty">No test discussions yet.</p>}{shown.map(thread => <article className={openThread?.conversation_id === thread.id ? 'session-card open' : 'session-card'} key={thread.id}><label className="session-pick"><input type="checkbox" checked={picked.threads.includes(String(thread.id))} onChange={event => setPicked({ ...picked, threads: event.target.checked ? [...picked.threads, String(thread.id)] : picked.threads.filter(id => id !== String(thread.id)) })} />Select</label><button type="button" className="text-button" onClick={() => void (async () => { const response = await fetch(`${API}/api/v1/conversations/${thread.id}`); if (response.ok) { setOpenThread(await response.json()); setSellerReply(''); } })()}>Session {thread.id}</button><p>{thread.preview}</p><button type="button" className="text-button" onClick={() => void (async () => { const response = await fetch(`${API}/api/v1/conversations/${thread.id}`); if (!response.ok) return; const body = await response.json() as { conversation_id: number; turns: { role: string; text: string }[] }; setConversationId(body.conversation_id); setTurns(body.turns.map(turn => ({ role: turn.role === 'buyer' ? 'buyer' : 'draft', text: turn.text }))); setPage('agents'); })()}>Continue</button>{openThread?.conversation_id === thread.id && <div className="session-thread">{openThread.turns.map((turn, index) => <p key={index} className={turn.role === 'buyer' ? 'buyer-turn' : 'draft-turn'}><b>{turn.role === 'buyer' ? 'Buyer' : turn.role === 'seller' ? 'You' : 'Agent'}</b>{turn.text}</p>)}<form className="instruction-form" onSubmit={event => { event.preventDefault(); void (async () => { if (!sellerReply.trim() || !openThread) return; const response = await fetch(`${API}/api/v1/conversations/${openThread.conversation_id}/reply`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: sellerReply }) }); if (!response.ok) { setError(await errorMessage(response)); return; } setSellerReply(''); const again = await fetch(`${API}/api/v1/conversations/${openThread.conversation_id}`); if (again.ok) setOpenThread(await again.json()); })(); }}><textarea rows={3} placeholder="Your reply" value={sellerReply} onChange={event => setSellerReply(event.target.value)} /><button className="button primary" disabled={busy || !sellerReply.trim()}>Reply</button></form></div>}</article>)}<ScrollMore node={threadsMore.ref} more={shown.length < rows.length} /></>; })()}</div>
        </section>}
        {page === 'integrations' && <section className="panel integration-panel">
          <div className="panel-heading"><h2>Integrations</h2></div>
          <article className="instruction-card integration-row"><div><strong>WhatsApp</strong><p>Official Cloud API.</p></div><label className="switch"><input type="checkbox" checked={agentOn} disabled={agentSaving} onChange={event => { const next = event.target.checked; setAgentSaving(true); window.setTimeout(() => { setAgentOn(next); localStorage.setItem('agent-enabled', next ? 'on' : 'off'); setAgentSaving(false); }, 500); }} />{agentSaving ? <span className="reply-loading"><span className="reply-spinner"/>Saving</span> : <span>{agentOn ? 'On' : 'Off'}</span>}</label></article>
          <article className="instruction-card integration-row"><div><strong>Facebook</strong><p>Coming soon.</p></div><label className="switch"><input type="checkbox" disabled /></label></article>
        </section>}
      </div>
    </main>
  </div>;
}

async function errorMessage(response: Response) {
  try { const body = await response.json() as { detail?: string }; return body.detail ?? `Request failed (${response.status}).`; }
  catch { return `Request failed (${response.status}).`; }
}

export default App;

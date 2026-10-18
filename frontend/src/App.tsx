import { FormEvent, useCallback, useEffect, useState } from 'react';

type Product = {
  id: number;
  sku: string;
  shop_id: string;
  name: string;
  description: string;
  price_tnd: string | null;
  availability: 'available' | 'sold_out' | 'unknown';
};
type Attachment = '' | 'image' | 'voice' | 'video' | 'location';
type Instruction = {
  id: number;
  source_text: string;
  rules: string[];
  may_answer: string[];
  ask_seller: string[];
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
  const [turns, setTurns] = useState<{ role: string; text: string }[]>([]);
  const [order, setOrder] = useState<OrderProgress | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [productForm, setProductForm] = useState({ sku: '', name: '', description: '', price_tnd: '', availability: 'unknown' as Product['availability'] });
  const [showForm, setShowForm] = useState(false);

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

  useEffect(() => { void loadProducts(); void loadInstructions(); }, [loadProducts, loadInstructions]);

  async function saveProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const response = await fetch(`${API}/api/v1/products/${encodeURIComponent(productForm.sku)}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: productForm.name, description: productForm.description, price_tnd: productForm.price_tnd || null, availability: productForm.availability }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      setProductForm({ sku: '', name: '', description: '', price_tnd: '', availability: 'unknown' });
      setShowForm(false); await loadProducts();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Product save failed.'); }
    finally { setBusy(false); }
  }

  async function addInstruction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const response = await fetch(`${API}/api/v1/instructions`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: instructionText }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      setInstructionText('');
      await loadInstructions();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Instruction save failed.'); }
    finally { setBusy(false); }
  }

  async function removeInstruction(id: number) {
    setBusy(true); setError('');
    try {
      const response = await fetch(`${API}/api/v1/instructions/${id}`, { method: 'DELETE' });
      if (!response.ok && response.status !== 204) throw new Error(await errorMessage(response));
      await loadInstructions();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not remove the instruction.'); }
    finally { setBusy(false); }
  }

  async function createDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setDraft(null); setError('');
    if (!message.trim() && !attachment) {
      setError('Paste a customer message, or mark a photo, voice, video, or location.');
      setBusy(false);
      return;
    }
    try {
      const response = await fetch(`${API}/api/v1/replies/draft`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          ...(attachment ? { attachment } : {}),
          ...(conversationId ? { conversation_id: conversationId } : {}),
        }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const body = await response.json() as DraftResponse;
      setDraft(body);
      if (body.conversation_id) {
        setConversationId(body.conversation_id);
        const saved = body.draft.reply_text || body.draft.seller_question || '';
        setTurns(current => [
          ...current,
          { role: 'buyer', text: message.trim() },
          ...(saved ? [{ role: 'draft', text: saved }] : []),
        ]);
      }
      setOrder(body.order);
      setMessage('');
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Draft failed.'); }
    finally { setBusy(false); }
  }

  return <div className="app-shell">
    <header className="topbar">
      <a className="brand" href="#home" aria-label="Souk home"><span className="brand-mark">s</span><span>souq<span className="brand-dot">.</span></span></a>
      <div className="shop-switch"><span className="shop-avatar">D</span><span><b>Demo boutique</b><small>Seller workspace</small></span><span className="chevron">⌄</span></div>
      <div className="profile"><span className="status-dot"/> Demo mode</div>
    </header>

    <aside className="sidebar" aria-label="Main navigation">
      <span className="nav-label">WORKSPACE</span>
      <a className="nav-item active" href="#overview"><span className="nav-icon">▦</span>Overview</a>
      <a className="nav-item" href="#catalog"><span className="nav-icon">◇</span>Products <span className="nav-count">{products.length}</span></a>
      <a className="nav-item disabled" aria-disabled="true" title="Inbox integration is not available yet"><span className="nav-icon">▤</span>Conversations <span className="soon">Soon</span></a>
      <a className="nav-item" href="#instructions"><span className="nav-icon">✳</span>Shop knowledge <span className="nav-count">{instructions.length}</span></a>
      <div className="sidebar-bottom"><div className="api-note"><span className="note-dot"/>Local API connected<small>Drafts are never sent</small></div><small className="version">EARLY DEMO · v0.1</small></div>
    </aside>

    <main className="main" id="overview">
      <div className="welcome-row"><div><div className="eyebrow">TUESDAY, YOUR SHOP AT A GLANCE</div><h1>Good morning, seller <span>✳</span></h1><p className="subheading">Your product knowledge and reply copilot, in one place.</p></div><div className="today-pill"><span className="live-dot"/> Demo workspace</div></div>
      <section className="stats" aria-label="Shop summary">
        <article className="stat-card"><span className="stat-icon mint">◇</span><span className="stat-label">PRODUCTS</span><strong>{products.length.toString().padStart(2, '0')}</strong><small>In your approved catalog</small></article>
        <article className="stat-card"><span className="stat-icon peach">✳</span><span className="stat-label">REPLY COPILOT</span><strong className="stat-word">Ready</strong><small>Drafts for seller review</small></article>
        <article className="stat-card muted-card"><span className="stat-icon lavender">▤</span><span className="stat-label">CONVERSATIONS</span><strong className="stat-word">Not connected</strong><small>Messaging integration comes later</small></article>
      </section>

      {error && <div className="alert" role="alert"><span>!</span>{error}<button onClick={() => setError('')} aria-label="Dismiss">×</button></div>}

      <div className="content-grid">
        <section className="panel catalog-panel" id="catalog">
          <div className="panel-heading"><div><div className="eyebrow">YOUR SHOP KNOWLEDGE</div><h2>Product catalog <span className="count-badge">{products.length}</span></h2><p>Approved facts the assistant can use in drafts.</p></div><button className="button secondary add-button" onClick={() => setShowForm(!showForm)}><span>＋</span> Add product</button></div>
          {showForm && <form className="product-form" onSubmit={saveProduct}>
            <div className="form-header"><strong>Add approved product</strong><button type="button" className="close-button" onClick={() => setShowForm(false)} aria-label="Close">×</button></div>
            <div className="form-fields"><label>Product name<input required maxLength={160} value={productForm.name} onChange={e => { const name = e.target.value; setProductForm({ ...productForm, name, sku: name.trim().toLowerCase().replace(/\s+/g, '_') }); }} placeholder="e.g. Robe bleue" /><small>SKU generated automatically from the product name.</small></label><label className="wide">Description<textarea maxLength={2000} value={productForm.description} onChange={e => setProductForm({ ...productForm, description: e.target.value })} placeholder="Sizes, color, material…" rows={2}/></label><label>Price (TND)<input inputMode="decimal" value={productForm.price_tnd} onChange={e => setProductForm({ ...productForm, price_tnd: e.target.value })} placeholder="65.000" /></label><label>Availability<select value={productForm.availability} onChange={e => setProductForm({ ...productForm, availability: e.target.value as Product['availability'] })}><option value="unknown">Unknown</option><option value="available">Available</option><option value="sold_out">Sold out</option></select></label></div>
            <button className="button primary" disabled={busy}>{busy ? 'Saving…' : 'Save approved product'}</button>
          </form>}
          {products.length ? <div className="product-list">{products.map(product => <article className="product-row" key={product.id}><div className="product-thumb">{product.name.slice(0, 1).toUpperCase()}</div><div className="product-info"><strong>{product.name}</strong><span>{product.description || product.sku}</span><small>SKU · {product.sku}</small></div><div className="product-price">{product.price_tnd ? `${product.price_tnd} TND` : 'Price not set'}<span className={`availability ${product.availability}`}>{product.availability.replace('_', ' ')}</span></div></article>)}</div> : <div className="empty-state"><span className="empty-icon">◇</span><strong>Your catalog starts here</strong><p>Add a product with seller-confirmed details. The copilot only uses these approved facts.</p><button className="button primary" onClick={() => setShowForm(true)}>＋ Add your first product</button></div>}
          <button className="text-button" onClick={() => void loadProducts()}>↻ Refresh catalog</button>
          <div className="instruction-block" id="instructions">
            <div className="eyebrow">TEACH THE ASSISTANT</div>
            <h2>Seller instructions</h2>
            <p>Write how the shop works. A separate model turns the note into rules the assistant can answer from, so it does not ask you every time.</p>
            <form onSubmit={addInstruction}>
              <textarea maxLength={4000} rows={3} value={instructionText} onChange={event => setInstructionText(event.target.value)} placeholder="Example: Be warm. Delivery to Tunis is 7 TND. Ask me only for custom embroidery." required />
              <button className="button secondary" disabled={busy || !instructionText.trim()}>{busy ? 'Saving…' : 'Add instruction'}</button>
            </form>
            {instructions.map(item => <article className="instruction-card" key={item.id}><p>{item.source_text}</p>{item.may_answer.length > 0 && <ul>{item.may_answer.map(fact => <li key={fact}>{fact}</li>)}</ul>}<button type="button" className="text-button" onClick={() => void removeInstruction(item.id)}>Remove</button></article>)}
          </div>
        </section>

        <section className="panel copilot-panel">
          <div className="panel-heading"><div><div className="eyebrow">SELLER-REVIEWED</div><h2>Reply copilot <span className="sparkle">✳</span></h2><p>Draft a reply from approved product facts.</p></div><span className="draft-tag">DRAFT ONLY</span></div>
          <div className="thread-tools"><button type="button" className="text-button" onClick={() => { setConversationId(null); setTurns([]); setOrder(null); setDraft(null); setMessage(''); }}>New conversation</button></div>
          {turns.length > 0 && <div className="thread">{turns.map((turn, index) => <p key={`${turn.role}-${index}`} className={turn.role === 'buyer' ? 'buyer-turn' : 'draft-turn'}><b>{turn.role === 'buyer' ? 'Buyer' : 'Draft'}</b>{turn.text}</p>)}</div>}
          {order && <div className="order-progress"><span>Order</span><p>{order.product_name || 'Product missing'} · {order.size || 'size missing'}</p><p>{order.phone || 'Phone missing'} · {order.address || 'Address missing'}</p>{order.missing.length === 0 && <p>Ready for the buyer to confirm. The shop has not accepted it yet.</p>}</div>}
          <form onSubmit={createDraft} className="copilot-form"><label htmlFor="buyer-message">What did the customer ask?</label><textarea id="buyer-message" rows={5} maxLength={4000} value={message} onChange={event => setMessage(event.target.value)} placeholder="Paste a customer message…\n\nExample: Bonjour, est-ce que la robe bleue est disponible en taille M ?" /><div className="input-meta"><span>Draft follows the customer's language</span><span>{message.length}/4000</span></div><label htmlFor="buyer-attachment">Customer also shared</label><select id="buyer-attachment" value={attachment} onChange={event => setAttachment(event.target.value as Attachment)}><option value="">Nothing else</option><option value="image">A photo</option><option value="voice">A voice message</option><option value="video">A video</option><option value="location">A location</option></select><button className="button primary draft-button" disabled={busy || (!message.trim() && !attachment)}>{busy ? <><span className="spinner"/> Preparing draft…</> : <>✳ Draft a reply <span>→</span></>}</button></form>
          {draft && <div className={`draft-result ${draft.draft.needs_seller ? 'needs-seller' : ''}`} aria-live="polite"><div className="result-heading"><span className="result-icon">{draft.draft.needs_seller ? '!' : '✓'}</span><div><strong>{draft.draft.needs_seller ? 'Seller input needed' : 'Draft ready for your review'}</strong><small>{draft.draft.needs_seller ? 'No customer response was sent.' : 'Review and copy it into your messaging app.'}</small></div></div>{draft.draft.reply_text && <blockquote>{draft.draft.reply_text}</blockquote>}{draft.draft.seller_question && <div className="seller-question"><span>Question for you</span><p>{draft.draft.seller_question}</p></div>}{draft.draft.used_instruction_ids.length > 0 && !draft.draft.needs_seller && <div className="result-meta">Answered from your instructions</div>}<div className="result-meta">{draft.model} · {draft.latency_ms} ms · {draft.usage.total_tokens} tokens</div></div>}
          <div className="privacy-note"><span>↗</span><p><b>You stay in control.</b> Drafts are not sent automatically. Unknown facts go back to you instead of being guessed.</p></div>
        </section>
      </div>
      <footer className="footer"><span>Made for small shops in Tunisia <span className="heart">♥</span></span><span>Demo only · No Facebook or WhatsApp connection</span></footer>
    </main>
  </div>;
}

async function errorMessage(response: Response) {
  try { const body = await response.json() as { detail?: string }; return body.detail ?? `Request failed (${response.status}).`; }
  catch { return `Request failed (${response.status}).`; }
}

export default App;

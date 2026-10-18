import { useEffect, useRef, useState } from 'react';
import { Button } from '@toss/tds-mobile';
import { addItem, errors, loadItems, MAX_ITEMS, removeItem, resetItems, saveItems } from './domain/items';
import { planSpin, resultMessage } from './domain/spin';
import { platform } from './platform';
import { Wheel } from './Wheel';

export default function App() {
  const [path, setPath] = useState(window.location.pathname);
  const shell = useRef<HTMLElement>(null);
  useEffect(() => { const onPop = () => setPath(window.location.pathname); window.addEventListener('popstate', onPop); return () => window.removeEventListener('popstate', onPop); }, []);
  useEffect(() => { if (shell.current) shell.current.scrollTop = 0; }, [path]);
  function navigate(next: string) { window.history.pushState(null, '', next); setPath(next); }
  return <main className="app-shell" ref={shell}>
    {path === '/privacy' || path === '/terms' ? <article className="policy">
      <p className="eyebrow">오늘의 선택 룰렛</p>
      <h1>{path === '/privacy' ? '개인정보처리방침' : '이용약관'}</h1>
      {path === '/privacy' ? <>
        <h2>개인정보를 수집하지 않아요</h2><p>이 서비스는 회원가입 없이 사용할 수 있으며, 개인정보를 수집하거나 서버로 전송하지 않습니다.</p>
        <h2>메뉴는 이 기기에만 저장돼요</h2><p>입력한 메뉴는 기기의 브라우저 저장소에만 저장됩니다. 브라우저의 사이트 데이터를 지우면 삭제되며, 기본값으로 초기화하면 저장된 메뉴가 기본 메뉴로 바뀝니다.</p>
        <h2>복사와 공유는 직접 선택해요</h2><p>결과 복사 또는 공유하기를 누를 때만 결과 문구를 클립보드나 선택한 공유 앱에 전달합니다.</p>
      </> : <>
        <h2>가벼운 점심 고민을 도와드려요</h2><p>메뉴를 등록하고 무작위로 하나를 선택하는 서비스입니다. 모든 메뉴의 선택 확률은 같으며 결과는 참고용으로 이용해 주세요.</p>
        <h2>기기 안에서 동작해요</h2><p>개인정보를 수집하지 않으며 메뉴 데이터는 기기 내에만 저장됩니다. 저장소를 삭제하거나 기기를 바꾸면 메뉴가 유지되지 않을 수 있습니다.</p>
        <h2>이용 안내</h2><p>다른 사람의 개인정보나 권리를 침해하는 내용을 입력하지 마세요. 기기와 앱 환경에 따라 진동, 복사, 공유 기능이 지원되지 않을 수 있습니다.</p>
      </>}
      <p className="muted">시행일: 2026년 10월 18일</p>
      <Button onClick={() => navigate('/')}>룰렛으로 이동</Button>
    </article> : <Roulette navigate={navigate} />}
  </main>;
}

function Roulette({ navigate }: { navigate(path: string): void }) {
  const [items, setItems] = useState(loadItems);
  const [input, setInput] = useState('');
  const [error, setError] = useState('');
  const [storageWarning, setStorageWarning] = useState('');
  const [spinning, setSpinning] = useState(false);
  const [angle, setAngle] = useState(0);
  const [duration, setDuration] = useState(3600);
  const [winner, setWinner] = useState<string | null>(null);
  const [toast, setToast] = useState('');
  const [busy, setBusy] = useState(false);
  const locked = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const dialog = useRef<HTMLDialogElement>(null);
  const spinButton = useRef<HTMLDivElement>(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => {
    if (winner && dialog.current && !dialog.current.open) dialog.current.showModal();
  }, [winner]);
  useEffect(() => {
    if (!toast) return;
    const timeout = setTimeout(() => setToast(''), 4500);
    return () => clearTimeout(timeout);
  }, [toast]);
  function update(next: string[]) {
    if (locked.current) return;
    setItems(next); setError('');
    setStorageWarning(saveItems(next) ? '' : '메뉴를 저장하지 못했어요. 다음에 열면 기본 메뉴로 시작할 수 있어요.');
  }
  function add() {
    if (locked.current) return;
    const next = addItem(items, input);
    if (next.error) { setError(errors[next.error]); return; }
    update(next.items); setInput('');
  }
  function closeResult() { dialog.current?.close(); setWinner(null); spinButton.current?.querySelector('button')?.focus(); }
  function spin() {
    if (locked.current || items.length < 2) return;
    closeResult(); setToast(''); locked.current = true; setSpinning(true);
    const next = planSpin(items.length, angle);
    const ms = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 120 : 3600;
    setDuration(ms); setAngle(next.angle);
    timer.current = setTimeout(() => {
      locked.current = false; setSpinning(false); setWinner(items[next.winner]);
      void platform.haptic('success');
    }, ms);
  }
  async function send(kind: 'copy' | 'share') {
    if (!winner || busy) return;
    setBusy(true);
    const result = await platform[kind](resultMessage(winner));
    if (result.via === 'cancelled') { setBusy(false); return; }
    setToast(result.ok ? (result.via === 'clipboard' || kind === 'copy' ? '결과를 복사했어요.' : '공유 창을 열었어요.') : '복사 또는 공유를 사용할 수 없어요. 메뉴 이름을 직접 확인해 주세요.');
    setBusy(false);
  }
  return <>
    <section className="intro">
      <p className="eyebrow">오늘의 선택 룰렛</p>
      <h1>오늘 점심,<br />뭐 먹을까요?</h1>
      <p className="muted">고민은 짧게, 점심은 맛있게.</p>
    </section>
    <section className="roulette-section" aria-label="점심 메뉴 선택">
      <Wheel items={items} angle={angle} duration={duration} />
      <p className="wheel-caption">{spinning ? '맛있는 선택을 기다려 주세요…' : `${items.length}개의 메뉴 · 모두 같은 확률`}</p>
      <div ref={spinButton}><Button size="xlarge" display="block" disabled={spinning || items.length < 2} onClick={spin}>{spinning ? '고르는 중…' : '돌리기'}</Button></div>
      {items.length < 2 && <p className="notice" role="status">메뉴를 2개 이상 넣어 주세요.</p>}
    </section>
    <section className="editor" aria-labelledby="editor-title">
      <div className="section-heading"><h2 id="editor-title">메뉴 편집 <span>{items.length}/12</span></h2><button className="text-button" disabled={spinning} onClick={() => { update(resetItems()); setInput(''); }}>기본값으로 초기화</button></div>
      <form onSubmit={event => { event.preventDefault(); add(); }}>
        <label className="sr-only" htmlFor="menu">추가할 메뉴</label>
        <input id="menu" value={input} onChange={event => { setInput(event.target.value); setError(''); }} placeholder="먹고 싶은 메뉴를 넣어 주세요" disabled={spinning || items.length >= MAX_ITEMS} aria-invalid={!!error} aria-describedby="input-help" autoComplete="off" />
        <Button type="submit" disabled={spinning || items.length >= MAX_ITEMS}>추가</Button>
      </form>
      <p id="input-help" className={error ? 'error' : 'hint'} aria-live="polite">{error || (items.length >= MAX_ITEMS ? errors.full : '최대 12개 · 메뉴 이름은 20자까지')}</p>
      <ul className="menu-list">{items.map((item, index) => <li key={item}><span>{item}</span><button disabled={spinning} aria-label={`${item} 삭제`} onClick={() => update(removeItem(items, index))}>×</button></li>)}</ul>
      {storageWarning && <p role="status" className="notice">{storageWarning}</p>}
    </section>
    <footer><p>메뉴는 내 기기에만 저장돼요</p><a href="/privacy" onClick={e => { e.preventDefault(); navigate('/privacy'); }}>개인정보처리방침</a><span aria-hidden="true">·</span><a href="/terms" onClick={e => { e.preventDefault(); navigate('/terms'); }}>이용약관</a></footer>
    <div className="sr-only" aria-live="polite">{winner ? `오늘 점심은 ${winner}입니다.` : ''}</div>
    {winner && <dialog ref={dialog} className="result" aria-labelledby="result-title" onCancel={closeResult}>
      <div className="result-emoji" aria-hidden="true">🍽️</div><p className="muted">오늘 점심은 이걸로!</p><h2 id="result-title">{winner}</h2>
      <Button display="block" size="xlarge" onClick={spin}>다시 돌리기</Button>
      <div className="result-actions"><Button variant="weak" aria-disabled={busy} onClick={() => void send('copy')}>결과 복사</Button><Button variant="weak" aria-disabled={busy} onClick={() => void send('share')}>공유하기</Button></div>
      <button className="text-button close" onClick={closeResult}>닫기</button>
      {toast && <p className="feedback" role="status">{toast}</p>}
    </dialog>}
    {toast && !winner && <p className="toast" role="status">{toast}</p>}
  </>;
}


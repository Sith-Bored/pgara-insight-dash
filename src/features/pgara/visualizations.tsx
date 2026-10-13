import { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, LabelList } from 'recharts';
import { ChartNoAxesColumnIncreasing, Network, ListTree, Table2, Check, Loader2, FlaskConical } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { algorithms, type AlgorithmId, type AlgorithmResult } from './types';
import { useExperiment } from './experiment-context';
import { Panel } from './controls';
import { toUiAlgorithm } from '@/services/pgara-backend';
function selectedResult(results: AlgorithmResult[] | undefined, selected: AlgorithmId) {
  return results?.find(result => toUiAlgorithm(result.algorithm) === selected) ?? results?.[0];
}
export function ResultEmpty() { const s=useExperiment(); return <div className="empty-state" role="status">{s.loading?<Loader2 className="loading-spin"/>:<FlaskConical/>}<div className="text-foreground mb-2">{s.loading?'Running allocation experiment':'No allocation results'}</div><div>{s.loading?'Waiting for the experiment response…':'Run an experiment to populate this view.'}</div></div>; }
function ChartTooltip({active,payload,label}:{active?:boolean;payload?:Array<{name?:string;value?:number|string}>;label?:string|number}) { if(!active||!payload?.length) return null; return <div className="chart-tooltip"><div className="text-foreground mb-2">{label}</div>{payload.map((p,i)=><div key={i} className="text-muted-foreground">{p.name}: {Number(p.value).toLocaleString()} spill ops</div>)}</div>; }
/** Zero stays zero. A degenerate 0–0 axis is given a tick at 0 so the baseline remains visible. */
export function spillChartScale(values: number[]) {
  const allZero = values.length > 0 && values.every(value => value === 0);
  return allZero
    ? { allZero: true, domain: [0, 1] as [number, number], ticks: [0] }
    : { allZero: false, domain: [0, 'dataMax'] as [number, 'dataMax'], ticks: undefined };
}
function spillLabel(value: unknown) {
  return typeof value === 'number' ? value.toLocaleString() : '';
}
export function ComparisonChart({byProfile=false}:{byProfile?:boolean}) {
  const s=useExperiment();
  const rows=s.result?.results.flatMap(r=>{const algorithm=toUiAlgorithm(r.algorithm); return algorithm?[{name:algorithms.find(a=>a.id===algorithm)?.short ?? algorithm,spillOps:r.dynamicSpillOps,algorithm}]:[];})??[];
  const profiles=s.result?.results[0]?.profileCosts.map((p,i)=>({name:p.profile,...Object.fromEntries((s.result?.results??[]).flatMap(r=>{const algorithm=toUiAlgorithm(r.algorithm); return algorithm?[[algorithm,r.profileCosts[i]?.spillOps??0]]:[]}))}))??[];
  const shown=algorithms.filter(a=>s.result?.results.some(r=>toUiAlgorithm(r.algorithm)===a.id));
  const values=byProfile
    ? profiles.flatMap(row=>shown.flatMap(a=>{const value=(row as Record<string, string | number>)[a.id]; return typeof value==='number'?[value]:[];}))
    : rows.map(row=>row.spillOps);
  const scale=spillChartScale(values);
  return <Panel title={byProfile?'Profile-by-profile spill cost':'Algorithm comparison'} icon={<ChartNoAxesColumnIncreasing/>} action={<span className="badge">Dynamic spill operations</span>}>
    {s.result?<><div className="panel-body"><div className="comparison-legend mb-4">{shown.map(a=>{const cost=rows.find(row=>row.algorithm===a.id)?.spillOps; return <span key={a.id}><i className={`algo-dot ${a.color}`}/>{a.short}{!byProfile && cost!==undefined && <span className="font-mono">{cost.toLocaleString()}</span>}</span>;})}</div><div className="chart">{scale.allZero && <p className="chart-zero-note" role="status">No estimated spills for this configuration.</p>}<ResponsiveContainer width="100%" height="100%"><BarChart data={byProfile?profiles:rows} margin={{top:16,right:8,left:-14,bottom:0}} barCategoryGap={byProfile?'25%':'28%'}><CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 4"/><XAxis dataKey="name" axisLine={false} tickLine={false} tickMargin={12}/><YAxis axisLine={false} tickLine={false} domain={scale.domain} {...(scale.ticks ? { ticks: scale.ticks } : {})} allowDecimals={false} tickFormatter={v=>v>=1000?`${v/1000}k`:String(v)}/><Tooltip cursor={{fill:'var(--muted)'}} content={<ChartTooltip/>}/>{byProfile?shown.map(a=><Bar key={a.id} dataKey={a.id} name={a.short} fill={`var(--${a.color})`} radius={[3,3,0,0]}><LabelList position="top" formatter={spillLabel}/></Bar>):shown.map(a=><Bar key={a.id} dataKey={row=>row.algorithm===a.id?row.spillOps:null} name={a.short} fill={`var(--${a.color})`} radius={[3,3,0,0]} stackId="algorithms"><LabelList position="top" formatter={spillLabel}/></Bar>)}</BarChart></ResponsiveContainer></div></div><div className="chart-foot"><span>{s.result.source==='sample'?'Illustrative fixture · k = 4 · λ = 0.60':'Sum of estimated spill operations across the supplied profiles'}{scale.allZero && s.result.source==='backend'?' · returned zeros, not missing data':''}</span><span>{s.result.source==='sample'?'Not a measured benchmark':'Not measured runtime'}</span></div></>:<ResultEmpty/>}
  </Panel>;
}
export function Assignments() {
  const s=useExperiment(); const [algorithm,setAlgorithm]=useState<AlgorithmId>('game');
  const current=selectedResult(s.result?.results, algorithm);
  const currentId=current ? toUiAlgorithm(current.algorithm) ?? algorithm : algorithm;
  return <Panel title="Register allocation" icon={<Table2/>} action={s.result&&<select aria-label="Assignment algorithm" className="select-input" value={currentId} onChange={e=>{ const id=toUiAlgorithm(e.target.value); if(id)setAlgorithm(id); }}>{s.result.results.map(r=>{const id=toUiAlgorithm(r.algorithm); return id?<option key={id} value={id}>{algorithms.find(a=>a.id===id)?.short}</option>:null;})}</select>}>
    {current?<><div className="table-scroll"><table className="data-table"><thead><tr><th>Virtual register</th><th>Physical register</th><th>Live range</th><th className="numeric">Profile weight</th></tr></thead><tbody>{current.assignments.map(a=><tr key={a.virtual}><td className="font-mono">{a.virtual}</td><td>{a.physical?<span className="font-mono text-primary">{a.physical}</span>:<span className="badge sample">Spilled</span>}</td><td className="font-mono text-muted-foreground">{a.liveRange}</td><td className="numeric text-muted-foreground">{a.weight.toLocaleString()}</td></tr>)}</tbody></table></div><div className="chart-foot"><span>{current.assignments.filter(a=>a.physical).length} assigned · {current.spills.length} spilled · {current.dynamicSpillOps.toLocaleString()} {s.result?.source==='sample'?'illustrative spill ops':'estimated spill ops'}</span><span className="font-mono">{current.executionMs.toFixed(2)} ms</span></div></>:<ResultEmpty/>}
  </Panel>;
}
export function InterferenceGraph({large=false}:{large?:boolean}) {
  const s=useExperiment(); const [selected,setSelected]=useState<string|null>(null); const [algorithm,setAlgorithm]=useState<AlgorithmId>('game');
  const current=selectedResult(s.result?.results, algorithm);
  const currentId=current ? toUiAlgorithm(current.algorithm) ?? algorithm : algorithm;
  const graph=s.result?.graph;
  return <Panel title="Interference graph" icon={<Network/>} action={large&&s.result?<select aria-label="Graph algorithm" className="select-input" value={currentId} onChange={e=>{const id=toUiAlgorithm(e.target.value);if(id)setAlgorithm(id);}}>{s.result.results.map(r=>{const id=toUiAlgorithm(r.algorithm); return id?<option key={id} value={id}>{algorithms.find(a=>a.id===id)?.short}</option>:null;})}</select>:<span className="badge">{graph?.nodes.length??0} nodes · {graph?.edges.length??0} edges</span>}>
    {graph?<><div className="graph-wrap"><svg className={`graph-svg ${large?'min-h-96':''}`} viewBox="0 0 390 290" role="group" aria-label="Virtual register interference graph">{graph.edges.map(([a,b],i)=>{const from=graph.nodes.find(n=>n.id===a);const to=graph.nodes.find(n=>n.id===b);return from&&to?<line key={i} x1={from.x} y1={from.y} x2={to.x} y2={to.y} className="graph-edge" opacity={selected&&(a!==selected&&b!==selected)?0.2:1}/>:null;})}{graph.nodes.map(n=>{const assignment=current?.assignments.find(a=>a.virtual===n.id); const physical=assignment?.physical;const register=physical?Number(physical.replace(/\D/g,'')):null;return <g key={n.id} role="button" tabIndex={0} aria-label={`Inspect ${n.id}, ${physical??'spilled'}`} onClick={()=>setSelected(selected===n.id?null:n.id)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();setSelected(selected===n.id?null:n.id);}}}><circle cx={n.x} cy={n.y} r={21} className={`graph-node ${register===null?'spilled':`register-${register%4}`} ${selected===n.id?'selected':''}`}/><text x={n.x} y={n.y+4} textAnchor="middle" className="graph-text">{n.id}</text></g>;})}</svg></div><div className="graph-legend">{(s.result?.source==='backend'?['p0','p1','p2','p3','Spilled']:['R0','R1','R2','R3','Spilled']).map(r=><span className="graph-key" key={r}><i/>{r}</span>)}</div><div className="chart-foot">{selected?<span><span className="font-mono text-primary">{selected}</span> · {graph.edges.filter(e=>e.includes(selected)).length} interfering live ranges · {current?.assignments.find(a=>a.virtual===selected)?.physical??'spilled'}</span>:<span>{algorithms.find(a=>a.id===currentId)?.short} · interference relationships</span>}<span className="font-mono">G = (V, E)</span></div></>:<ResultEmpty/>}
  </Panel>;
}
function traceLabel(source: 'sample' | 'backend' | undefined, status: string | undefined, ready: boolean) {
  if (!ready) return 'No trace';
  if (source === 'sample') return 'Illustrative sequence';
  if (status === 'no_improving_move') return 'Local equilibrium';
  if (status === 'iteration_budget') return 'Iteration budget';
  if (status === 'single_pass') return 'Single pass';
  return 'Returned trace';
}
export function DecisionTrace({full=false}:{full?:boolean}) {
  const s=useExperiment(); const [step,setStep]=useState(0); const gameAvailable=s.result?.results.some(r=>toUiAlgorithm(r.algorithm)==='game'); const trace=gameAvailable?s.result?.trace??[]:[];
  const label = traceLabel(s.result?.source, s.result?.traceStatus, trace.length > 0);
  return <Panel title="Allocation decision trace" icon={<ListTree/>} action={<span className={s.result?.source==='sample'?'badge sample':'badge'}>{s.result?.source==='sample'&&<Check size={10}/>}{label}</span>}>
    {s.result&&trace.length?<><div>{(full?trace:trace.slice(0,3)).map((t,i)=><div className="trace-item" key={t.step}><span className={`trace-step ${full&&step===i?'text-primary border-primary':''}`}>{String(t.step).padStart(2,'0')}</span><div className="flex-1"><div className="flex justify-between gap-3"><h3>{t.action}</h3>{full&&<span className="font-mono text-violet text-xs">Φ = {t.potential.toLocaleString()}</span>}</div><p>{t.detail}</p>{full&&<span className="badge mt-2">{t.status}</span>}</div></div>)}</div>{full&&<><div className="panel-body"><div className="field-label"><span>Decision {step+1} of {trace.length}</span><span className="font-mono text-violet">Φ = {trace[step]?.potential.toLocaleString()}</span></div><input aria-label="Trace decision step" type="range" className="w-full" min="0" max={Math.max(0,trace.length-1)} value={step} onChange={e=>setStep(Number(e.target.value))}/><div className="flex justify-between mt-3"><Button variant="outline" size="sm" disabled={step===0} onClick={()=>setStep(v=>v-1)}>Previous</Button><Button variant="outline" size="sm" disabled={step===trace.length-1} onClick={()=>setStep(v=>v+1)}>Next decision</Button></div></div><div className="chart panel-body"><ResponsiveContainer width="100%" height="100%"><LineChart data={trace}><CartesianGrid stroke="var(--border)" vertical={false}/><XAxis dataKey="step" axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false} width={40}/><Tooltip content={<div className="chart-tooltip">{s.result?.source==='sample'?'Illustrative potential · not a measurement':'Estimated potential · not measured runtime'}</div>}/><Line dataKey="potential" stroke="var(--violet)" strokeWidth={2} dot={{fill:'var(--violet)',r:3}} isAnimationActive={false}/></LineChart></ResponsiveContainer></div></> }<div className="chart-foot"><span>Multi-Profile Potential Game</span><span className="font-mono">{s.result.source==='sample'?'Illustrative sequence':label}</span></div></>:s.result?<div className="empty-state">Select Multi-Profile Potential Game and run an experiment to see its decision trace.</div>:<ResultEmpty/>}
  </Panel>;
}
const apiNames: Record<string, string> = { static_greedy: 'Static Greedy', profile_greedy: 'Profile-Weighted Greedy', potential_game: 'Potential Game' };
export function BenchmarkTable() {
  const s=useExperiment();return <Panel title={s.result?.source==='backend'?'This program’s allocation':'Illustrative algorithm results'} icon={<Table2/>} action={<span className="badge">{s.result?.source==='sample'?'Sample fixture':'Estimated spill operations'}</span>}>{s.result?<div className="table-scroll"><table className="data-table"><thead><tr><th>Algorithm</th><th className="numeric">Assigned</th><th>Spilled live ranges</th><th className="numeric">Estimated spill ops</th><th className="numeric">Allocator time (ms)</th></tr></thead><tbody>{s.result.results.map(r=>{const id=toUiAlgorithm(r.algorithm); return <tr key={id??r.algorithm}><td>{id?algorithms.find(a=>a.id===id)?.name:r.algorithm}</td><td className="numeric">{r.assignments.filter(a=>a.physical).length}</td><td className="font-mono text-warning">{r.spills.join(', ')||'None'}</td><td className="numeric">{r.dynamicSpillOps.toLocaleString()}</td><td className="numeric">{r.executionMs.toFixed(2)}</td></tr>;})}</tbody></table></div>:<ResultEmpty/>}</Panel>;
}
export function SyntheticBenchmark() {
  const s = useExperiment();
  if (s.settings.mode !== 'backend') {
    return <Panel title="Synthetic allocator suite" icon={<FlaskConical/>}><div className="empty-state">This suite runs only after you connect the backend and run an experiment. The table above is the fixed illustrative fixture, not a measurement.</div></Panel>;
  }
  return <Panel title="Synthetic allocator suite" icon={<FlaskConical/>} action={<span className="badge">POST /api/benchmark</span>}>
    {s.benchmarkLoading && <div className="empty-state" role="status"><Loader2 className="loading-spin"/><div>Running the built-in synthetic programs…</div></div>}
    {!s.benchmarkLoading && s.benchmarkError && <div className="empty-state" role="alert">{s.benchmarkError}</div>}
    {!s.benchmarkLoading && !s.benchmarkError && !s.benchmark && <div className="empty-state">Run an experiment to execute the synthetic suite. It does not run when you only change configuration.</div>}
    {s.benchmark && !s.benchmarkLoading && <><p className="panel-body text-xs text-muted-foreground leading-6">{s.benchmark.note}</p><p className="panel-body text-xs text-muted-foreground leading-6">Each case uses the tradeoff shown in this table. The robustness slider applies only to the program allocation.</p><div className="table-scroll"><table className="data-table"><thead><tr><th>Case</th><th>Algorithm</th><th className="numeric">k</th><th>Tradeoff</th><th>Spilled live ranges</th><th className="numeric">Estimated spill ops</th><th className="numeric">Allocator time (ms)</th></tr></thead><tbody>{s.benchmark.cases.flatMap(item => item.rows.map(row => <tr key={`${item.name}-${row.algorithm}`}><td className="benchmark-case"><div>{item.name}</div><small>{item.description}</small></td><td>{apiNames[row.algorithm] ?? row.algorithm}</td><td className="numeric">{item.numRegisters}</td><td className="font-mono">{item.tradeoff}</td><td className="font-mono text-warning">{row.spills.join(', ') || 'None'}</td><td className="numeric">{row.spillOps.toLocaleString()}</td><td className="numeric">{row.executionMs.toFixed(2)}</td></tr>))}</tbody></table></div></>}
  </Panel>;
}

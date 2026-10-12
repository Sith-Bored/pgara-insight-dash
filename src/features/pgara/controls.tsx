import { useState } from 'react';
import { Braces, SlidersHorizontal, FileCode2, RotateCcw, Play, Loader2, ChartNoAxesColumnIncreasing } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { algorithms } from './types';
import { blockLabels } from '@/services/pgara-backend';
import { useExperiment } from './experiment-context';
import type { ReactNode } from 'react';
export function Panel({title,icon,action,children,className=''}:{title:string;icon?:ReactNode;action?:ReactNode;children:ReactNode;className?:string}) { return <section className={`panel ${className}`}><header className="panel-header"><h2 className="panel-title">{icon}{title}</h2>{action}</header>{children}</section>; }
export function RunButton({compact=false}:{compact?:boolean}) { const s=useExperiment(); return <Button onClick={s.run} disabled={s.loading} size={compact?'sm':'default'}>{s.loading?<Loader2 className="loading-spin"/>:<Play/>}{s.loading?'Running experiment…':'Run Allocation Experiment'}</Button>; }
export function Configuration() {
  const s=useExperiment();
  return <Panel title="Experiment configuration" icon={<SlidersHorizontal/>} action={<span className="badge">CONFIG</span>}>
    <div className="panel-body">
      <label className="field-label" htmlFor="register-count">Physical registers <span className="font-mono text-primary">k = {s.registers}</span></label>
      <div className="register-control"><input aria-label="Register count slider" type="range" min="1" max="16" value={s.registers} disabled={s.loading} onChange={e=>s.update(s.setRegisters,Number(e.target.value))}/><input id="register-count" className="number-input" type="number" min="1" max="16" value={s.registers} disabled={s.loading} onChange={e=>s.update(s.setRegisters,Number(e.target.value))}/></div>
      <div className="range-markers"><span>1 register</span><span>16 registers</span></div>
      <div className="divider"/>
      <div className="field-label">Allocation algorithms <span className="text-muted-foreground">{s.selected.length} selected</span></div>
      {algorithms.map(a=><label className="algorithm-option" key={a.id}><input type="checkbox" checked={s.selected.includes(a.id)} disabled={s.loading} onChange={e=>s.update(s.setSelected,e.target.checked?[...s.selected,a.id]:s.selected.filter(id=>id!==a.id))}/><span><span className={`algo-dot ${a.color} mr-2`}/>{a.name}<small>{a.id==='static'?'Unweighted interference-based allocation':a.id==='weighted'?'Optimize for the dominant execution profile':'Balance allocation cost across multiple profiles'}</small></span></label>)}
      <div className="divider"/>
      <label className="field-label" htmlFor="robustness">Multi-profile robustness <span className="font-mono text-violet">λ = {s.robustness.toFixed(2)}</span></label>
      <input className="w-full" id="robustness" type="range" min="0" max="1" step="0.05" value={s.robustness} disabled={s.loading} onChange={e=>s.update(s.setRobustness,Number(e.target.value))}/>
      <div className="flex justify-between field-help mt-1"><span>Expected cost</span><span>Worst-profile cost</span></div>
    </div>
    <div className="config-footer"><RunButton/><div className="field-help text-center mt-2">{s.settings.mode==='sample'?'Sample mode · fixed illustrative results':'Analysis backend · runs only when you click'}</div></div>
  </Panel>;
}
export function ProgramEditor({large=false}:{large?:boolean}) {
  const s=useExperiment(); const [scroll,setScroll]=useState(0);
  const blocks = blockLabels(s.program);
  return <Panel title="Program editor" icon={<FileCode2/>} action={<Button size="sm" variant="ghost" disabled={s.loading} onClick={()=>void s.loadSample()}><RotateCcw/>Load sample</Button>}>
    <div className="code-toolbar"><span className="flex items-center gap-2"><Braces size={12}/>sample_program.tac</span><span>Three-address code</span></div>
    <div className={`code-editor ${large?'large':''}`}><div className="line-numbers" aria-hidden="true"><div style={{transform:`translateY(-${scroll}px)`}}>{s.program.split('\n').map((_,i)=><div key={i}>{i+1}</div>)}</div></div><textarea aria-label="Three-address code program" spellCheck={false} value={s.program} disabled={s.loading} onScroll={e=>setScroll(e.currentTarget.scrollTop)} onChange={e=>s.update(s.setProgram,e.target.value)}/></div>
    <div className="code-footer"><span>TAC · UTF-8</span><span>{s.program.split('\n').length} lines · {blocks.length} blocks</span></div>
  </Panel>;
}
const dashboardPaths = ['Entry', 'Hot path', 'Cold path', 'Exit'];
export function ExecutionProfiles({editable=false}:{editable?:boolean}) {
  const s=useExperiment(); const [active,setActive]=useState(0);
  const labels = blockLabels(s.program);
  const index = Math.min(active, Math.max(s.profiles.length - 1, 0));
  const profile = s.profiles[index];
  if (!profile) return null;
  const rows = labels.length ? labels : profile.frequencies.map((_, i) => `B${i}`);
  const namedPaths = rows.length === 4 && rows.every((label, i) => label === `B${i}`);
  const max = Math.max(1, ...profile.frequencies.filter((count): count is number => typeof count === 'number'));
  return <Panel title="Execution profile" icon={<ChartNoAxesColumnIncreasing/>} action={<span className="badge">{s.profiles.length} profiles</span>}>
    <div className="profile-tabs">{s.profiles.map((p,i)=><Button variant="ghost" key={`${p.name}-${i}`} className={i===index?'active':''} onClick={()=>setActive(i)}>{p.name}</Button>)}</div>
    {labels.length === 0 && <div className="empty-state">Add a `block name:` header to attach an execution count to each basic block.</div>}
    {labels.length > 0 && <div className="table-scroll"><table className="data-table"><thead><tr><th>Basic block</th><th>Path</th><th className="numeric">Executions</th><th>Frequency</th></tr></thead><tbody>{rows.map((label,i)=>{const count=profile.frequencies[i]; const shown=typeof count==='number'?count.toLocaleString():'—'; return <tr key={label}><td className="font-mono text-primary">{label}</td><td className="text-muted-foreground">{namedPaths ? dashboardPaths[i] : '—'}</td><td className="numeric">{editable?<input aria-label={`${profile.name} ${label} executions`} className="number-input w-24" type="number" min="0" value={count ?? ''} disabled={s.loading} onChange={e=>{const next=Number(e.target.value); s.update(s.setProfiles,s.profiles.map((p,j)=>j!==index?p:{...p,frequencies:rows.map((_,k)=>k===i?next:p.frequencies[k])}));}}/>:shown}</td><td><div className="profile-bar"><progress value={typeof count==='number'?count:0} max={max}/></div></td></tr>;})}</tbody></table></div>}
    <div className="chart-foot"><span>Explicit block execution counts · one per basic block</span><span className="font-mono">{rows.length} blocks</span></div>
  </Panel>;
}

import { useState } from 'react';
import { Braces, SlidersHorizontal, FileCode2, RotateCcw, Play, Loader2, ChartNoAxesColumnIncreasing } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { algorithms, sampleProgram } from './types';
import { useExperiment } from './experiment-context';
import type { ReactNode } from 'react';
export function Panel({title,icon,action,children,className=''}:{title:string;icon?:ReactNode;action?:ReactNode;children:ReactNode;className?:string}) { return <section className={`panel ${className}`}><header className="panel-header"><h2 className="panel-title">{icon}{title}</h2>{action}</header>{children}</section>; }
export function RunButton({compact=false}:{compact?:boolean}) { const s=useExperiment(); return <Button onClick={s.run} disabled={s.loading} size={compact?'sm':'default'}>{s.loading?<Loader2 className="loading-spin"/>:<Play/>}{s.loading?'Running experiment…':'Run Allocation Experiment'}</Button>; }
export function Configuration() {
  const s=useExperiment();
  return <Panel title="Experiment configuration" icon={<SlidersHorizontal/>} action={<span className="badge">CONFIG</span>}>
    <div className="panel-body">
      <label className="field-label" htmlFor="register-count">Physical registers <span className="font-mono text-primary">k = {s.registers}</span></label>
      <div className="register-control"><input aria-label="Register count slider" type="range" min="2" max="16" value={s.registers} disabled={s.loading} onChange={e=>s.update(s.setRegisters,Number(e.target.value))}/><input id="register-count" className="number-input" type="number" min="2" max="16" value={s.registers} disabled={s.loading} onChange={e=>s.update(s.setRegisters,Number(e.target.value))}/></div>
      <div className="range-markers"><span>2 registers</span><span>16 registers</span></div>
      <div className="divider"/>
      <div className="field-label">Allocation algorithms <span className="text-muted-foreground">{s.selected.length} selected</span></div>
      {algorithms.map(a=><label className="algorithm-option" key={a.id}><input type="checkbox" checked={s.selected.includes(a.id)} disabled={s.loading} onChange={e=>s.update(s.setSelected,e.target.checked?[...s.selected,a.id]:s.selected.filter(id=>id!==a.id))}/><span><span className={`algo-dot ${a.color} mr-2`}/>{a.name}<small>{a.id==='static'?'Unweighted interference-based allocation':a.id==='weighted'?'Optimize for the dominant execution profile':'Balance allocation cost across multiple profiles'}</small></span></label>)}
      <div className="divider"/>
      <label className="field-label" htmlFor="robustness">Multi-profile robustness <span className="font-mono text-violet">λ = {s.robustness.toFixed(2)}</span></label>
      <input className="w-full" id="robustness" type="range" min="0" max="1" step="0.05" value={s.robustness} disabled={s.loading} onChange={e=>s.update(s.setRobustness,Number(e.target.value))}/>
      <div className="flex justify-between field-help mt-1"><span>Expected cost</span><span>Worst-profile cost</span></div>
    </div>
    <div className="config-footer"><RunButton/><div className="field-help text-center mt-2">{s.settings.mode==='sample'?'Sample mode · fixed illustrative results':'Analysis backend · live API request'}</div></div>
  </Panel>;
}
export function ProgramEditor({large=false}:{large?:boolean}) {
  const s=useExperiment(); const [scroll,setScroll]=useState(0);
  return <Panel title="Program editor" icon={<FileCode2/>} action={<Button size="sm" variant="ghost" disabled={s.loading} onClick={()=>s.update(s.setProgram,sampleProgram)}><RotateCcw/>Load sample</Button>}>
    <div className="code-toolbar"><span className="flex items-center gap-2"><Braces size={12}/>sample_program.tac</span><span>Three-address code</span></div>
    <div className={`code-editor ${large?'large':''}`}><div className="line-numbers" aria-hidden="true"><div style={{transform:`translateY(-${scroll}px)`}}>{s.program.split('\n').map((_,i)=><div key={i}>{i+1}</div>)}</div></div><textarea aria-label="Three-address code program" spellCheck={false} value={s.program} disabled={s.loading} onScroll={e=>setScroll(e.currentTarget.scrollTop)} onChange={e=>s.update(s.setProgram,e.target.value)}/></div>
    <div className="code-footer"><span>TAC · UTF-8</span><span>{s.program.split('\n').length} lines · {s.program.match(/^\s*\w+:/gm)?.length ?? 0} blocks</span></div>
  </Panel>;
}
export function ExecutionProfiles({editable=false}:{editable?:boolean}) {
  const s=useExperiment(); const [active,setActive]=useState(0); const profile=s.profiles[active];
  if(!profile) return null;
  const max=Math.max(...profile.frequencies,1);
  return <Panel title="Execution profile" icon={<ChartNoAxesColumnIncreasing/>} action={<span className="badge">{s.profiles.length} profiles</span>}>
    <div className="profile-tabs">{s.profiles.map((p,i)=><Button variant="ghost" key={p.name} className={i===active?'active':''} onClick={()=>setActive(i)}>{p.name}</Button>)}</div>
    <div className="table-scroll"><table className="data-table"><thead><tr><th>Basic block</th><th>Path</th><th className="numeric">Executions</th><th>Frequency</th></tr></thead><tbody>{profile.frequencies.map((f,i)=><tr key={i}><td className="font-mono text-primary">B{i}</td><td className="text-muted-foreground">{['Entry','Hot path','Cold path','Exit'][i]}</td><td className="numeric">{editable?<input aria-label={`${profile.name} B${i} executions`} className="number-input w-20" type="number" min="0" value={f} disabled={s.loading} onChange={e=>s.update(s.setProfiles,s.profiles.map((p,j)=>j===active?{...p,frequencies:p.frequencies.map((v,k)=>k===i?Number(e.target.value):v)}:p))}/>:f.toLocaleString()}</td><td><div className="profile-bar"><progress value={f} max={max}/></div></td></tr>)}</tbody></table></div>
    <div className="chart-foot"><span>Block execution counts · per program invocation</span>{!editable&&<span className="font-mono">f(B)</span>}</div>
  </Panel>;
}

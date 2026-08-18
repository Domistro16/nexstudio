'use strict';
const fs=require('fs'),path=require('path');
function die(code,detail){process.stdout.write(JSON.stringify({ok:false,code,detail})+'\n');process.exit(0)}
const input=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
const root=process.env.STUDIO_STICKMAN_ENGINE_ROOT;if(!root)die('STICKMAN_ENGINE_ROOT_NOT_CONFIGURED','');
const C=require(path.join(root,'cast/runtime/nexstick-cast-v2.js'));
function text(v){return String(v||'').toLowerCase()}
function mapAction(a){
 const v=String(a.execution?.resolved_verb||a.requested_verb||'').toUpperCase(),prop=text(a.prop),target=text(a.target),requirements=new Set((a.available_requirements||[]).map(x=>String(x)));
 if(v==='HOLD')return 'idle';
 if(v==='WALK')return 'walk';
 if(v==='RUN')return 'run';
 if(v==='PRESENT'&&requirements.has('presentation_prop')&&/(paper|papers|note|notes|card|document)/.test(prop))return 'presenter_papers';
 if(v==='TYPE'&&requirements.has('typing_surface')&&/(keyboard|laptop|computer)/.test(`${prop} ${target}`))return 'typing_leanback';
 if(v==='PHONE_HOLD'&&requirements.has('phone_prop')&&/(phone|mobile|handset)/.test(prop))return 'phone_talk';
 if(v==='REACH'&&requirements.has('high_reach_target')&&/(high|above|upper|top|overhead)/.test(target))return 'high_reach';
 return null;
}
const board=input.finalBoard||{},beats=board.beats||[];if(board.schema!=='NexMindCanonicalSoundStoryboardV4'||!beats.length)die('P8_FINAL_BOARD_SCHEMA_UNSUPPORTED','');
function dur(b,f){const d=b.editorial?.duration;if(d&&Number(d.value)>=0&&Number(d.rate)>0)return Math.max(.25,Number(d.value)/Number(d.rate));return f}
function cast(actor){const r=C.resolveCast(actor);if(r.status!=='RESOLVED')die('STICKMAN_CAST_SELECTION_REQUIRED',JSON.stringify({actor,status:r.status,warnings:r.warnings}));const slot=r.slots?.[0],spec=slot?.final_cast_spec;if(!spec)die('STICKMAN_CAST_SELECTION_REQUIRED',actor);return spec}
const totalReq=Number(input.durationSeconds||60),fallback=totalReq/beats.length;let cursor=0,clips=[];
for(const b of beats){if(b.motion_plan_status!=='DIRECTED_MOTION_PERFORMANCE'||b.sound_plan_status!=='DIRECTED_SOUND')die('P8_FINAL_BOARD_DEPARTMENTS_UNRESOLVED',b.beat_id);const bd=dur(b,fallback),acts=(b.motion_actions||[]).filter(x=>x.performer_class==='STICKMAN_V2');if(!acts.length)die('STICKMAN_BEAT_REQUIRES_STICKMAN_ACTION',b.beat_id);const by=new Map();for(const a of acts){const v=String(a.execution?.resolved_verb||a.requested_verb||'').toUpperCase(),mapped=mapAction(a);if(!mapped)die('STICKMAN_MOTION_BINDING_UNSUPPORTED',`${b.beat_id}:${v}`);if(a.contact_requirement&&a.contact_requirement!=='NONE')die('STICKMAN_CONTACT_ACTION_NEEDS_EXPLICIT_ENGINE_TARGET',`${b.beat_id}:${v}:${a.contact_requirement}`);const actor=String(a.actor||'').trim();if(!actor)die('STICKMAN_ACTOR_REQUIRED',b.beat_id);if(!by.has(actor))by.set(actor,[]);by.get(actor).push({action:mapped,personality:'calm',transitionDuration:.2});}
 const performers=[];for(const [actor,steps] of by){const spec=cast(actor),seq=C.sequence({familyId:spec.family,steps:steps.map(x=>({...x,personality:spec.personality?.selected_preset||'calm',roleTags:[spec.clothing?.selected_tag].filter(Boolean)}))},{qa:{fps:60,maxFootSlideM:.02,maxHorizontalAccelMps2:15,maxHorizontalJerkMps3:200}});if(seq.blocked)die('STICKMAN_SEQUENCE_BLOCKED',`${actor}:${seq.failure}`);const qa=seq.qa();if(!qa?.pass)die('STICKMAN_SEQUENCE_QA_BLOCKED',JSON.stringify({actor,qa}));performers.push({actor,spec,seq});}
 clips.push({beat:b,start:cursor,duration:bd,performers});cursor+=bd;}
const ratio=String(input.aspectRatio||'16:9'),dims=ratio==='1:1'?[900,900]:ratio==='9:16'?[720,1280]:[1280,720],W=dims[0],H=dims[1],fps=6,frames=Math.max(2,Math.ceil(cursor*fps));
function clipAt(t){return clips.find(c=>c.start<=t&&t<c.start+c.duration)||clips[clips.length-1]}
for(let i=0;i<frames;i++){const t=Math.min(cursor-.0001,i/fps),cl=clipAt(t),local=Math.max(0,t-cl.start),n=cl.performers.length;let imgs='';for(let j=0;j<n;j++){const p=cl.performers[j],st=p.seq.sample(Math.min(p.seq.duration,(local/cl.duration)*p.seq.duration));if(!st||st.blocked)die('STICKMAN_RENDER_STATE_BLOCKED',st?.failure||'null');const cellW=n===1?W:W/n,cellH=H,svg=C.render(st,{width:Math.round(cellW),height:cellH}),b64=Buffer.from(svg).toString('base64');imgs+=`<image x="${Math.round(j*cellW)}" y="0" width="${Math.round(cellW)}" height="${cellH}" href="data:image/svg+xml;base64,${b64}"/>`;}
 const scene=`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><rect width="100%" height="100%" fill="#f7f5ef"/>${imgs}</svg>`;fs.writeFileSync(path.join(out,`frame-${String(i).padStart(5,'0')}.svg`),scene)}
process.stdout.write(JSON.stringify({ok:true,width:W,height:H,fps,duration:cursor,frames,beats:clips.map(c=>({beatId:c.beat.beat_id,start:c.start,duration:c.duration,performers:c.performers.map(p=>({actor:p.actor,family:p.spec.family}))}))})+'\n');

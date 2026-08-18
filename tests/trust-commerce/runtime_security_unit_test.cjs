const fs=require('fs'),path=require('path'),os=require('os'),crypto=require('crypto');
let ts; try{ts=require('typescript')}catch{ts=require('/opt/nvm/versions/node/v22.16.0/lib/node_modules/typescript/lib/typescript.js')}
process.env.NODE_ENV='test';process.env.STUDIO_TRUST_SECRET='0123456789abcdef0123456789abcdef';process.env.STUDIO_PAYMENT_PROVIDER='stripe';process.env.STRIPE_SECRET_KEY='sk_test_runtime_security';process.env.STRIPE_WEBHOOK_SECRET='whsec_runtime_security';
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'studio-trust-unit-'));
for(const file of ['env.ts','payment-provider.ts','upload-security.ts']){const src=fs.readFileSync(path.join(process.cwd(),'src/lib',file),'utf8');const js=ts.transpileModule(src,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText;fs.writeFileSync(path.join(tmp,file.replace(/\.ts$/,'.js')),js)}
const payment=require(path.join(tmp,'payment-provider.js'));const upload=require(path.join(tmp,'upload-security.js'));
const tests=[];function test(name,fn){try{fn();tests.push({name,ok:true})}catch(e){tests.push({name,ok:false,detail:String(e&&e.message||e)})}}
function stripeHeader(body,timestamp=Math.floor(Date.now()/1000)){const sig=crypto.createHmac('sha256',process.env.STRIPE_WEBHOOK_SECRET).update(`${timestamp}.${body}`).digest('hex');return `t=${timestamp},v1=${sig}`}
const body=JSON.stringify({id:'evt_1',type:'checkout.session.completed',data:{object:{id:'cs_1',payment_status:'paid',amount_total:100,currency:'usd',client_reference_id:'intent'}}});
test('valid Stripe signature accepted',()=>{if(payment.verifyStripeWebhook(body,stripeHeader(body)).id!=='evt_1')throw Error('wrong event')});
test('tampered Stripe payload rejected',()=>{let ok=false;try{payment.verifyStripeWebhook(body+'x',stripeHeader(body))}catch{ok=true}if(!ok)throw Error('accepted tamper')});
test('stale Stripe signature rejected',()=>{const t=Math.floor(Date.now()/1000)-1000;let ok=false;try{payment.verifyStripeWebhook(body,stripeHeader(body,t))}catch{ok=true}if(!ok)throw Error('accepted stale')});
test('PNG magic detected independent of filename',()=>{const b=Buffer.from([0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a,1,2]);if(upload.inspectUpload(b,'image/png').detectedMime!=='image/png')throw Error('not png')});
test('declared MIME mismatch rejected',()=>{const b=Buffer.from([0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a,1,2]);let ok=false;try{upload.inspectUpload(b,'image/jpeg')}catch{ok=true}if(!ok)throw Error('accepted mismatch')});
test('active PDF content rejected',()=>{let ok=false;try{upload.inspectUpload(Buffer.from('%PDF-1.7\n1 0 obj << /OpenAction 2 0 R >>'),'application/pdf')}catch(e){ok=String(e.message).includes('ACTIVE_CONTENT')}if(!ok)throw Error('accepted active PDF')});
test('unsafe upload filename is normalized',()=>{const n=upload.safeUploadName('../../evil\0\n.pdf');if(n.includes('/')||n.includes('\\')||n.includes('\0')||n.includes('\n'))throw Error('unsafe name')});
const failed=tests.filter(t=>!t.ok);console.log(JSON.stringify({schema:'StudioTrustRuntimeSecurityUnit V1',pass:!failed.length,passed:tests.length-failed.length,total:tests.length,tests},null,2));process.exit(failed.length?1:0);

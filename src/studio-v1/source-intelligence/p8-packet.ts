type AnyRecord = Record<string, unknown>;
function record(value:unknown):AnyRecord{return value&&typeof value==="object"&&!Array.isArray(value)?value as AnyRecord:{};}
function array(value:unknown):unknown[]{return Array.isArray(value)?value:[];}
function terms(value:string){return new Set(value.toLowerCase().match(/[a-z0-9][a-z0-9_-]{2,}/g)?.filter(x=>!new Set(["the","and","for","with","from","this","that","into","your","you","are","was","were","have","has","will","make","video","film"]).has(x))||[]);}
function scoreSegment(segment:AnyRecord,promptTerms:Set<string>,index:number){
  const text=String(segment.text||"").toLowerCase();let score=index===0?4:0;
  if(String(segment.kind||"")==="table")score+=3;
  if(/title|heading|summary|overview|conclusion|result|finding/i.test(String(segment.locator||"")))score+=2;
  for(const term of promptTerms)if(text.includes(term))score+=2;
  return score;
}

export type P8SourcePacket={
  summaries:Array<{id:string;kind:string;label:string|null;summary:string|null}>;
  evidence:Array<{claim_id:string;claim:string;source:string;status:string}>;
  visualReferences:Array<{sourceId:string;sourceLabel:string;page:number|null;locator:string;role:string;visuallyComplex:boolean;visualOnly:boolean;objectKey:string;mimeType:string;sha256:string}>;
  warnings:string[];
  extractedSourceCount:number;
  contextChars:number;
};

export function buildP8SourcePacket(input:{rawSources:unknown;productionInputs:unknown[];prompt:string;maxContextChars?:number}):P8SourcePacket{
  const raw=array(input.rawSources).map(record);const persisted=array(input.productionInputs).map(record);const promptTerms=terms(input.prompt||"");
  const byOrdinal=new Map<number,AnyRecord>();for(const item of persisted)byOrdinal.set(Number(item.ordinal||0),item);
  const summaries:P8SourcePacket["summaries"]=[];const evidence:P8SourcePacket["evidence"]=[];const visualReferences:P8SourcePacket["visualReferences"]=[];const warnings:string[]=[];
  const budget=Math.max(20_000,Math.min(Number(input.maxContextChars||160_000),260_000));let used=0;let extractedSourceCount=0;
  for(let ordinal=0;ordinal<raw.length;ordinal++){
    const source=raw[ordinal];const inputRow=byOrdinal.get(ordinal)||{};const persistedSource=record(inputRow.source);const extracted=record(persistedSource.extracted);
    const id=String(source.id||inputRow.sourceId||`source-${ordinal+1}`);const kind=String(source.kind||inputRow.kind||"UNKNOWN");const label=String(source.label||inputRow.label||persistedSource.name||`Source ${ordinal+1}`).slice(0,300)||null;
    const reference=typeof source.reference==="string"?source.reference.slice(0,4000):typeof inputRow.reference==="string"?String(inputRow.reference).slice(0,4000):null;
    if(extracted.schema==="StudioSourceIntelligenceV1"&&extracted.status==="EXTRACTED"){
      extractedSourceCount+=1;const segments=array(extracted.segments).map(record);const ranked=segments.map((seg,index)=>({seg,index,score:scoreSegment(seg,promptTerms,index)})).sort((a,b)=>b.score-a.score||a.index-b.index);
      const mandatory=new Set<number>();if(segments.length)mandatory.add(0);for(let i=0;i<segments.length;i++)if(String(segments[i].kind||"")==="table")mandatory.add(i);
      const chosen=[...ranked.filter(x=>mandatory.has(x.index)),...ranked.filter(x=>!mandatory.has(x.index))].filter((x,i,a)=>a.findIndex(y=>y.index===x.index)===i).slice(0,24);
      const outline=segments.slice(0,80).map(seg=>String(seg.locator||seg.segmentId||"")).filter(Boolean).join("; ").slice(0,6000);
      summaries.push({id:`${id}:document`,kind:`${kind}:SOURCE_INTELLIGENCE`,label,summary:`${String(extracted.documentKind||"DOCUMENT")} source. Provenance-preserving outline: ${outline}${array(extracted.warnings).length?` Warnings: ${array(extracted.warnings).join(", ")}`:""}`.slice(0,7000)});
      for(const item of chosen){
        const seg=item.seg;const text=String(seg.text||"");if(!text)continue;const prefix=`[${label||id} :: ${String(seg.locator||seg.segmentId||"segment")} :: sha256 ${String(seg.sha256||"")}] `;const room=budget-used;if(room<300)break;const claim=(prefix+text).slice(0,Math.min(7000,room));used+=claim.length;
        const segmentId=String(seg.segmentId||`seg-${item.index+1}`);summaries.push({id:`${id}:${segmentId}`,kind:`${kind}:EXTRACTED_SEGMENT`,label:`${label||id} — ${String(seg.locator||segmentId)}`.slice(0,300),summary:claim});
        evidence.push({claim_id:`${id}:${segmentId}`,claim:text.slice(0,6500),source:`${label||id} :: ${String(seg.locator||segmentId)} :: sha256 ${String(seg.sha256||"")}`,status:"USER_SOURCE_EXTRACTED"});
      }
      const visualOnlyPages=new Set(array(extracted.visualOnlyPages).map(Number).filter(x=>Number.isInteger(x)&&x>0));
      const visualEvidencePages=new Set(array(extracted.visualEvidencePages).map(Number).filter(x=>Number.isInteger(x)&&x>0));
      for(const previewValue of array(extracted.visualPreviews)){
        const preview=record(previewValue);const objectKey=String(preview.objectKey||"");const sha256=String(preview.sha256||"");const pageValue=preview.page==null?null:Number(preview.page);const page=pageValue!==null&&Number.isInteger(pageValue)&&pageValue>0?pageValue:null;
        if(objectKey&&sha256)visualReferences.push({sourceId:id,sourceLabel:label||id,page,locator:String(preview.locator|| (page?`page ${page}`:"embedded visual")),role:String(preview.role||"EMBEDDED_IMAGE"),visuallyComplex:Boolean(preview.visuallyComplex)||(page!==null&&visualEvidencePages.has(page)),visualOnly:page!==null&&visualOnlyPages.has(page),objectKey,mimeType:String(preview.mimeType||"image/png"),sha256});
      }
      if(String(extracted.visualCoverage||"NONE")!=="FULL"&&Number(extracted.pageCount||0)>0)warnings.push(`${id}:SOURCE_VISUAL_COVERAGE_${String(extracted.visualCoverage||"NONE")}`);
      if(used>=budget)warnings.push("SOURCE_INTELLIGENCE_CONTEXT_BUDGET_REACHED");
    } else {
      const fallback=[label,reference].filter(Boolean).join(": ").slice(0,4500)||null;summaries.push({id,kind,label,summary:fallback});
      if(persistedSource.id&&["application/pdf","application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/vnd.openxmlformats-officedocument.presentationml.presentation"].includes(String(persistedSource.detectedMimeType||persistedSource.mimeType||"")))warnings.push(`${id}:SOURCE_INTELLIGENCE_NOT_READY`);
    }
  }
  visualReferences.sort((a,b)=>Number(b.visualOnly)-Number(a.visualOnly)||Number(b.visuallyComplex)-Number(a.visuallyComplex)||(a.page??999999)-(b.page??999999));
  return{summaries:summaries.slice(0,120),evidence:evidence.slice(0,120),visualReferences:visualReferences.slice(0,120),warnings:[...new Set(warnings)],extractedSourceCount,contextChars:used};
}

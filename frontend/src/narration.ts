// Keep the complete explanation within each existing audio request's size limit.
export function narrationChunks(text:string,limit=3500):string[]{
 const chunks:string[]=[];
 let remaining=text;
 while(remaining.length>limit){
  let split=remaining.lastIndexOf('\n',limit);
  if(split<limit/2)split=remaining.lastIndexOf(' ',limit);
  if(split<=0)split=limit;
  chunks.push(remaining.slice(0,split));remaining=remaining.slice(split);
 }
 if(remaining)chunks.push(remaining);
 return chunks;
}

// One-off migration using the provisioned database and official Neon HTTPS SDK.
import {readFileSync,writeFileSync} from 'node:fs';
import {neon} from '../output/cloud-tools/node_modules/@neondatabase/serverless/index.mjs';
process.loadEnvFile('output/vercel-production.env');
const sql=neon(process.env.DATABASE_URL_UNPOOLED);
const plan=JSON.parse(readFileSync('output/http-migration-plan.json','utf8'));
try {
  const tables=await sql.query('SELECT table_name FROM information_schema.tables WHERE table_schema=$1',[plan.schema]);
  if(tables.length)throw new Error('Target schema is populated; refusing to replace it.');
  if(plan.verify)await sql.query('CREATE SCHEMA IF NOT EXISTS newsroom_migration_check');
  console.log('Applying migration in an atomic transaction.',plan.schema);
  const result=await sql.transaction(plan.queries.map(q=>sql.query(q.query,q.params)));
  const names=Object.keys(plan.counts),counts={};
  for(let i=0;i<names.length;i++){
    counts[names[i]]=Number(result[result.length-names.length+i][0].count);
    if(counts[names[i]]!==plan.counts[names[i]])throw new Error('Row count mismatch: '+names[i]);
  }
  const report={schema:plan.schema,verified:true,counts,backup:plan.backup,discarded_stale_joins:plan.discarded_stale_joins,active_sessions_copied:false};
  writeFileSync(plan.verify?'output/vercel-migration-check.json':'output/vercel-migration.json',JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
  if(plan.verify)await sql.query('DROP SCHEMA newsroom_migration_check CASCADE');
}catch(error){
  // Never print SQL parameters, the connection string, passwords or account data.
  console.error(JSON.stringify({migration:'failed',error:error.name,code:error.code??null,
    reason:error.message.startsWith('Target schema')?error.message:undefined}));
  process.exitCode=1;
}

// Contraste diagnóstico: llama al gate existente sobre fixtures temporales.
import {mkdtempSync,mkdirSync,writeFileSync} from 'node:fs'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {checkWorkbench} from '/workspace/thyrox/src/packages/workbench/manifest.ts'
const base=mkdtempSync(join(tmpdir(),'orm-gate-'))
const run=join(base,'contract-probe-20261020T000000');mkdirSync(run)
const manifest={question:'fixture',instrument:'missing/subdir/probe.py',metric:'fixture',blind_to:'fixture',destination:'fixture',form:'measurement'}
writeFileSync(join(run,'manifest.json'),JSON.stringify(manifest))
writeFileSync(join(run,'probe.py'),'# An unrelated basename witness\n')
writeFileSync(join(run,'tests'),'This is a file, not a test directory\n')
writeFileSync(join(run,'outputs'),'This is a file, not an output directory\n')
const accepted=checkWorkbench(run)
if(accepted.length)throw new Error(JSON.stringify(accepted))
writeFileSync(join(run,'manifest.jsonl'),JSON.stringify({kind:'history',step:'measured'})+'\n')
const hidden=checkWorkbench(run)
if(hidden.length!==5)throw new Error(JSON.stringify(hidden))
const result={basename_alias_and_files_instead_of_dirs_accepted:accepted,jsonl_history_hides_valid_json:hidden}
console.log(JSON.stringify(result,null,2))
await Bun.write('/workspace/scratch/orm-taxonomy-continuation/gate-contrast.json',JSON.stringify(result,null,2)+'\n')

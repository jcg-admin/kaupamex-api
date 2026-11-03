// Lectura nativa reproducible; no crea tareas ni restaura un store desde exports.
import { execFileSync } from 'node:child_process'
import { writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const provider = process.env.THYROX_ROOT
if (!provider) throw new Error('THYROX_ROOT is required')
const root = resolve(provider)
const revision = execFileSync('git', ['-C', root, 'rev-parse', 'HEAD'], {encoding:'utf8'}).trim()
if (revision !== '9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f') throw new Error('Reconcile changed Provider revision first')
const {taskTools} = await import(pathToFileURL(join(root, 'src/packages/tools/src/tasks.ts')).href)
const {storePath} = await import(pathToFileURL(join(root, 'src/packages/observability/src/store.ts')).href)
const sessionId = '168b0fdf-bfe4-590b-b6c0-b6be124c124a'
const tools = taskTools({dbPath:storePath(),sessionId})
const context = {cwd:process.cwd(),sessionId,abort:new AbortController().signal,messages:[]}
const destination = resolve(dirname(fileURLToPath(import.meta.url)), '../outputs')
for (const id of ['737','738','1153','1154','322','1192','1441']) {
  const result = await tools.find((tool: {name:string}) => tool.name === 'TaskGet').run({task_id:id},context)
  if (result.isError) throw new Error(result.content)
  const task = JSON.parse(result.content)
  if (['737','738'].includes(id) && (task.owner !== 'codex-module-lifecycle' || task.blocked_by.length)) {
    throw new Error('Reconcile current ownership/dependencies before continuing')
  }
  writeFileSync(join(destination, `task-${id}.json`), JSON.stringify({
    interface:'taskTools({dbPath:storePath(),sessionId}).TaskGet.run',
    command:'THYROX_ROOT=<declared Provider root> bun run probes/native_task_snapshot.ts',
    invocation:{argv:process.argv,cwd:process.cwd(),THYROX_ROOT:root},
    observed_at:new Date().toISOString(),
    provider_revision:revision,sessionId,input:{task_id:id},task,
    scope:'Native read only; export is evidence, not replacement TaskStore authority',
  },null,2)+'\n')
  console.log(task.citation_id,task.status,task.owner)
}

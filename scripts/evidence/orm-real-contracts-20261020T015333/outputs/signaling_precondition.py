# Reutiliza la configuración de la sonda de cursor; no repite sus pruebas.
from pathlib import Path
source=Path(__file__).with_name('cursor_transaction_contract.py').read_text()
exec(compile(source.split('observer=psycopg.connect',1)[0], 'cursor_setup', 'exec'))
from orm.registry import signaling_table_names
expected=tuple(signaling_table_names())
statements=[]
def record(execute,sql,params,many,context):
 statements.append(sql)
 return execute(sql,params,many,context)
try:
 with connection.execute_wrapper(record):
  try:registry.setup_signaling()
  except RuntimeError as error:
   message=str(error)
  else:raise AssertionError('Empty QA unexpectedly has signaling tables')
 assert all(name in message for name in expected)
 assert len(statements)==1 and statements[0].lstrip().upper().startswith('SELECT')
 result={'case':'Registry.setup_signaling on prepared but unmigrated QA','missing_tables':list(expected),'expected_error':message,'sql_statement_count':len(statements),'only_select':True,'ddl_or_data_writes':False,'classification_scope':'actual persistence dependency; not an architectural impossibility'}
 print(json.dumps(result,ensure_ascii=False,indent=2))
 Path('/workspace/scratch/orm-real-contracts/signaling-precondition.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
finally:connection.close()

| ruta / caso | tipo | valor |
|---|---|---|
| psycopg directo: json object | dict | {'a': 1} |
| psycopg directo: jsonb object | str | '{"a": 1}' |
| psycopg directo: jsonb array | str | '[1, 2]' |
| psycopg directo: jsonb string | str | '"x"' |
| psycopg directo: jsonb number | str | '3' |
| psycopg directo: jsonb boolean | str | 'true' |
| psycopg directo: jsonb null | str | 'null' |
| psycopg directo: SQL NULL | NoneType | None |
| psycopg directo: jsonb -> (jsonb) | str | '"b"' |
| psycopg directo: jsonb ->> (text) | str | 'b' |
| cursor de Django: json object | dict | {'a': 1} |
| cursor de Django: jsonb object | str | '{"a": 1}' |
| cursor de Django: jsonb array | str | '[1, 2]' |
| cursor de Django: jsonb string | str | '"x"' |
| cursor de Django: jsonb number | str | '3' |
| cursor de Django: jsonb boolean | str | 'true' |
| cursor de Django: jsonb null | str | 'null' |
| cursor de Django: SQL NULL | NoneType | None |
| cursor de Django: jsonb -> (jsonb) | str | '"b"' |
| cursor de Django: jsonb ->> (text) | str | 'b' |
| execute_query del ORM: json object | dict | {'a': 1} |
| execute_query del ORM: jsonb object | dict | {'a': 1} |
| execute_query del ORM: jsonb array | list | [1, 2] |
| execute_query del ORM: jsonb string | str | 'x' |
| execute_query del ORM: jsonb number | int | 3 |
| execute_query del ORM: jsonb boolean | bool | True |
| execute_query del ORM: jsonb null | NoneType | None |
| execute_query del ORM: SQL NULL | NoneType | None |
| execute_query del ORM: jsonb -> (jsonb) | str | 'b' |
| execute_query del ORM: jsonb ->> (text) | str | 'b' |
| JSONField por QuerySet | dict | {'n': [1]} |
| Json leído por el recordset | dict | {'n': [1]} |
| Properties leído por el recordset | dict | {'tag': 'alpha'} |
| get_property_definition | dict | {'name': 'tag', 'type': 'char', 'string': 'Tag'} |
1 passed, 2 warnings in 3.32s

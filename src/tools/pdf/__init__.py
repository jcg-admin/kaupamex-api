"""Lectura y fusión de PDF — la raíz espejada de ``odoo/tools/pdf/``.

Adaptación de ``odoo/tools/pdf/__init__.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3), **con el mecanismo construido y no importado**.

**Por qué se construye.** La fuente envuelve ``pypdf`` —sus tres módulos
``_pypdf*.py`` son adaptadores de versión— y esa biblioteca está **excluida
del stack por decisión del ejecutor**: el proyecto tiene motor propio de PDF
(ADR-017, helpers de libharu en ``tools/pdf/*.c``). Excluida la biblioteca,
quedan dos caminos: declarar divergencia y renunciar a fusionar, o construir
el mecanismo. Se construye — es la postura que
``porte-completo-no-parcial`` fija cuando el stack no trae la pieza.

**Qué alcance tiene, medido y declarado.** Este lector entiende el PDF que
**nuestro** motor emite: libharu 2.4.6, ``%PDF-1.3``, objetos indirectos sin
comprimir y sin flujos de referencias cruzadas. Verificado sobre la salida
real de ``pdf_report`` y ``pdf_receipt``.

*Ciega a:* un PDF con flujo de referencias cruzadas (``/Type /XRef``, PDF
1.5+), con flujos de objetos (``/ObjStm``) o cifrado. Ninguno de los tres los
produce nuestro motor. Un PDF ajeno que los traiga levanta
:class:`PdfReadError` en vez de leerse a medias — que es la conducta que
distingue «no lo puedo leer» de «lo leí mal».

Los nombres son los de la fuente porque son los que sus consumidores usan:
``PdfFileReader``, ``PdfFileWriter``, ``PdfReadError``.
"""
import io
import re

__all__ = ['PdfFileReader', 'PdfFileWriter', 'PdfReadError']

#: Un objeto indirecto: ``N G obj … endobj``.
_OBJECT = re.compile(rb'(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj', re.S)

#: Una referencia indirecta dentro del cuerpo de un objeto: ``N G R``.
_REFERENCE = re.compile(rb'(\d+)\s+(\d+)\s+R\b')

#: El diccionario del trailer, del que sale la raíz del documento.
_TRAILER = re.compile(rb'trailer(.*?)(?:startxref|%%EOF)', re.S)

#: La entrada ``/Root N G R`` del trailer.
_ROOT = re.compile(rb'/Root\s+(\d+)\s+(\d+)\s+R')

#: Los hijos de un nodo del árbol de páginas.
_KIDS = re.compile(rb'/Kids\s*\[(.*?)\]', re.S)

#: Los mecanismos que este lector NO entiende, con el marcador que los delata.
_UNSUPPORTED = (
    (b'/ObjStm', 'flujos de objetos (PDF 1.5+)'),
    (b'/Encrypt', 'documento cifrado'),
)


class PdfReadError(Exception):
    """El documento no se puede leer — nombre de la fuente."""


class PdfFileReader:
    """Lee los objetos y las páginas de un PDF.

    ≙ ``PdfFileReader`` de la fuente, acotado a lo que sus consumidores de
    este árbol piden: ``numPages``, ``getPage`` y el acceso al ``trailer``.

    :param stream: un objeto binario legible, o los bytes del documento.
    :raises PdfReadError: si el documento usa un mecanismo que este lector no
        entiende, o si no tiene raíz.
    """

    def __init__(self, stream):
        raw = stream.read() if hasattr(stream, 'read') else stream
        if not raw.startswith(b'%PDF-'):
            raise PdfReadError('no empieza con la cabecera %PDF-')
        for marker, reason in _UNSUPPORTED:
            if marker in raw:
                raise PdfReadError('mecanismo no soportado: %s' % reason)

        self.raw = raw
        #: número de objeto → cuerpo, en bytes y sin el envoltorio ``obj``.
        self.objects = {int(num): body
                        for num, _gen, body in _OBJECT.findall(raw)}

        trailer = _TRAILER.search(raw)
        root = _ROOT.search(trailer.group(1) if trailer else raw)
        if root is None:
            raise PdfReadError('sin /Root: no hay catálogo que recorrer')
        self.trailer = {'/Root': int(root.group(1))}
        self._pages = self._collect_pages()

    @property
    def numPages(self):
        """Cuántas páginas tiene el documento."""
        return len(self._pages)

    def getPage(self, index):
        """El número de objeto de la página ``index``, base cero."""
        return self._pages[index]

    def _collect_pages(self):
        """Recorre el árbol de páginas desde el catálogo, en orden.

        El árbol admite nodos intermedios (``/Type /Pages``), así que el
        recorrido es en profundidad y no un barrido de ``/Type /Page``: el
        orden de ``/Kids`` **es** el orden de las páginas, y un barrido por
        tipo lo perdería.
        """
        catalog = self.objects.get(self.trailer['/Root'], b'')
        pages_ref = _REFERENCE.search(
            catalog[catalog.find(b'/Pages'):]) if b'/Pages' in catalog else None
        if pages_ref is None:
            raise PdfReadError('el catálogo no declara /Pages')
        return self._walk(int(pages_ref.group(1)), set())

    def _walk(self, number, seen):
        """Los números de objeto de las páginas bajo ``number``, en orden."""
        if number in seen:
            raise PdfReadError('ciclo en el árbol de páginas: objeto %s'
                               % number)
        seen.add(number)
        body = self.objects.get(number, b'')
        kids = _KIDS.search(body)
        if kids is None:
            return [number]
        found = []
        for child, _gen in _REFERENCE.findall(kids.group(1)):
            found.extend(self._walk(int(child), seen))
        return found


class PdfFileWriter:
    """Arma un PDF nuevo a partir de páginas de otros.

    ≙ ``PdfFileWriter`` de la fuente, acotado a
    ``appendPagesFromReader``/``addPage``/``write``, que es lo que
    ``_merge_pdfs`` usa.

    Cada página que entra arrastra los objetos a los que apunta —su contenido,
    sus recursos, sus fuentes— y todos se renumeran para que no choquen con
    los del documento que ya se estaba armando. Sin ese arrastre la página
    llegaría sin sus tipos y el visor la dibujaría en blanco.
    """

    def __init__(self):
        #: número nuevo → cuerpo ya renumerado.
        self._objects = {}
        #: números nuevos de las páginas, en orden.
        self._pages = []
        self._next = 3  # 1 es el catálogo y 2 el nodo raíz de páginas.

    def appendPagesFromReader(self, reader):
        """Añade **todas** las páginas de ``reader``, en su orden."""
        for index in range(reader.numPages):
            self.addPage((reader, reader.getPage(index)))

    def addPage(self, page):
        """Añade una página, con los objetos de los que depende.

        :param page: la tupla ``(reader, número)`` que devuelve
            :meth:`PdfFileReader.getPage` junto a su lector.
        """
        reader, number = page
        mapping = {}
        self._import(reader, number, mapping)
        self._pages.append(mapping[number])

    def _import(self, reader, number, mapping):
        """Copia el objeto y su descendencia, renumerando por el camino."""
        if number in mapping:
            return mapping[number]
        new_number = self._next
        self._next += 1
        mapping[number] = new_number
        body = reader.objects.get(number, b'')

        for child, _gen in _REFERENCE.findall(body):
            child = int(child)
            if child in reader.objects:
                self._import(reader, child, mapping)

        def renumber(match):
            old = int(match.group(1))
            return b'%d 0 R' % mapping.get(old, old)

        self._objects[new_number] = _REFERENCE.sub(renumber, body)
        return new_number

    def write(self, stream):
        """Escribe el documento en ``stream``, con su tabla de referencias."""
        pieces = [b'%PDF-1.3\n']
        offsets = {}

        def emit(number, body):
            offsets[number] = sum(len(piece) for piece in pieces)
            pieces.append(b'%d 0 obj\n' % number + body.strip() + b'\nendobj\n')

        kids = b' '.join(b'%d 0 R' % number for number in self._pages)
        emit(1, b'<< /Type /Catalog /Pages 2 0 R >>')
        emit(2, b'<< /Type /Pages /Kids [ %s ] /Count %d >>'
             % (kids, len(self._pages)))
        for number in sorted(self._objects):
            body = self._objects[number]
            if number in self._pages:
                # La página cuelga del nodo raíz nuevo, no del de su origen.
                body = re.sub(rb'/Parent\s+\d+\s+\d+\s+R', b'/Parent 2 0 R',
                              body)
            emit(number, body)

        start = sum(len(piece) for piece in pieces)
        total = self._next
        pieces.append(b'xref\n0 %d\n' % total)
        pieces.append(b'0000000000 65535 f \n')
        for number in range(1, total):
            pieces.append(b'%010d 00000 n \n' % offsets.get(number, 0))
        pieces.append(b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n'
                      b'%%%%EOF\n' % (total, start))
        stream.write(b''.join(pieces))
        return stream

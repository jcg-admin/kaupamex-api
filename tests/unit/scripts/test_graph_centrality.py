"""La centralidad, medida por conducta y no por su nombre.

Estos tests son **puros**: no tocan Django ni la base. Miden el instrumento
sobre grafos cuyo desenlace se conoce de antemano.

El control que discrimina es ``test_the_bridge_beats_the_popular_node``:
es el unico que cae si alguien sustituye Brandes por un conteo de grado.
Los demas pasarian igual con cualquiera de los dos, asi que su verde no
distingue «mide caminos» de «cuenta vecinos» — el sub-patron D de
``metrica-decide-la-conclusion.md``.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))

from graph_centrality import betweenness_centrality  # noqa: E402


class TestBetweennessCentrality:
    """Brandes — por cuantos caminos mas cortos pasa cada nodo."""

    def test_the_bridge_beats_the_popular_node(self):
        """EL CONTROL QUE DISCRIMINA — cae si esto contara vecinos.

        ``puente`` tiene grado 1 en salida y ``popular`` tiene grado 3. Un
        conteo de grado coronaria a ``popular``. Pero todo camino de la
        izquierda a la derecha pasa por ``puente``, y ninguno pasa por
        ``popular``: los tres a los que apunta son hojas.

        Es la razon medida por la que el algoritmo es Brandes y no el grado:
        la pregunta del porte es «cuanto desbloquea», no «a cuantos toca».
        """
        nodes = ['izq', 'puente', 'der', 'popular', 'h1', 'h2', 'h3']
        edges = {
            'izq': {'puente'},
            'puente': {'der'},
            'der': set(),
            'popular': {'h1', 'h2', 'h3'},
            'h1': set(), 'h2': set(), 'h3': set(),
        }
        centrality = betweenness_centrality(nodes, edges)
        assert centrality['puente'] > centrality['popular']
        assert centrality['popular'] == 0.0

    def test_a_leaf_is_worth_nothing(self):
        nodes = ['a', 'b', 'c']
        edges = {'a': {'b'}, 'b': {'c'}, 'c': set()}
        centrality = betweenness_centrality(nodes, edges)
        assert centrality['a'] == 0.0
        assert centrality['c'] == 0.0
        assert centrality['b'] == 1.0

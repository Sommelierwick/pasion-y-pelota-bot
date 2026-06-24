import unittest
from unittest.mock import patch, MagicMock
import logging

# Configuración básica de logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class TestContradictionDetector(unittest.TestCase):

    @patch('requests.get')
    @patch('requests.patch')
    def test_contradiction_detected(self, mock_patch, mock_get):
        from tools.editor_jefe import EditorJefe

        # Configurar Mock de WordPress posts anteriores (Simulación de posts publicados)
        mock_posts = [
            {
                "id": 1001,
                "title": {"rendered": "Baja de último minuto: Kylian Mbappé descartado ante Brasil por lesión"},
                "excerpt": {"rendered": "<p>El astro francés Kylian Mbappé sufrió una contractura en el muslo y no podrá jugar el partido de esta noche en el Mundial.</p>"}
            },
            {
                "id": 1002,
                "title": {"rendered": "Fórmula 1: Franco Colapinto clasifica 8vo en el GP de Austria"},
                "excerpt": {"rendered": "<p>Una gran jornada para el piloto argentino en el Red Bull Ring clasificando en zona de puntos.</p>"}
            }
        ]

        # Configurar Mock de la respuesta GET de WordPress
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_posts)
        
        # Configurar Mock de la respuesta PATCH de WordPress
        mock_patch.return_value = MagicMock(status_code=200)

        editor = EditorJefe()
        
        # Caso de prueba 1: Noticia que desmiente directamente la baja de Mbappé
        new_title = "¡Milagro en Francia! Kylian Mbappé se recupera y va desde el arranque ante Brasil"
        new_excerpt = "A pesar de los reportes previos sobre su lesión, el delantero del Real Madrid superó las pruebas médicas de último minuto y será el capitán de Francia hoy."
        
        logging.info("--- EJECUTANDO CASO 1: CONTRADICCIÓN DIRECTA ---")
        result = editor.retract_contradictory_posts(new_title, new_excerpt)
        
        # Debería haber encontrado contradicción y haber enviado un PATCH al post ID 1001
        self.assertTrue(result)
        mock_patch.assert_called_with(
            f"{editor.wp_url}/wp-json/wp/v2/posts/1001",
            json={"status": "draft"},
            auth=editor.auth,
            timeout=15
        )

    @patch('requests.get')
    def test_no_contradiction_detected(self, mock_get):
        from tools.editor_jefe import EditorJefe

        # Configurar Mock de WordPress posts anteriores
        mock_posts = [
            {
                "id": 1001,
                "title": {"rendered": "Baja de último minuto: Kylian Mbappé descartado ante Brasil por lesión"},
                "excerpt": {"rendered": "<p>El astro francés Kylian Mbappé sufrió una contractura en el muslo y no podrá jugar el partido de esta noche en el Mundial.</p>"}
            }
        ]

        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_posts)

        editor = EditorJefe()
        
        # Caso de prueba 2: Noticia independiente (Fórmula 1)
        new_title = "Franco Colapinto finaliza 7mo y suma puntos valiosos en Austria"
        new_excerpt = "El piloto de Williams completó una gran carrera defensiva aguantando los ataques de Lewis Hamilton."
        
        logging.info("--- EJECUTANDO CASO 2: NOTICIA SIN CONTRADICCIÓN ---")
        result = editor.retract_contradictory_posts(new_title, new_excerpt)
        
        # No debería encontrar contradicción
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()

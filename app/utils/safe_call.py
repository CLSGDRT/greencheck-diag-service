import requests
from typing import Optional, Callable, Any
import time
from multiprocessing import Process, Queue

class SafeCall:
    def __init__(self, http_timeout: float = 10, http_retries: int = 2, http_backoff: float = 1.0):
        """
        Wrapper universel pour HTTP et exécution locale de modèles.
        
        http_timeout : timeout par requête HTTP en secondes
        http_retries  : nombre de tentatives pour HTTP
        http_backoff  : délai entre retries pour HTTP
        """
        self.http_timeout = http_timeout
        self.http_retries = http_retries
        self.http_backoff = http_backoff

    # -----------------------------
    # HTTP GET sécurisé
    # -----------------------------
    def http_get(self, url: str, headers: Optional[dict] = None, params: Optional[dict] = None) -> Optional[requests.Response]:
        attempt = 0
        while attempt <= self.http_retries:
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=self.http_timeout)
                resp.raise_for_status()
                return resp
            except requests.exceptions.Timeout:
                print(f"⏱ Timeout sur {url}, tentative {attempt+1}/{self.http_retries}")
            except requests.exceptions.RequestException as e:
                print(f"❌ Erreur HTTP sur {url} : {e}")
            attempt += 1
            time.sleep(self.http_backoff)
        return None

    # -----------------------------
    # Exécution locale sécurisée
    # -----------------------------
    def run_local(self, func: Callable, args: tuple = (), timeout: float = 300, fallback: Any = None) -> Any:
        """
        Exécute une fonction locale avec timeout (en secondes). Utilise multiprocessing pour pouvoir interrompre.
        
        func    : fonction à exécuter
        args    : tuple d’arguments
        timeout : temps max d’exécution
        fallback: valeur renvoyée si timeout ou exception
        """
        def wrapper(q, *args):
            try:
                result = func(*args)
                q.put(result)
            except Exception as e:
                q.put(e)

        q = Queue()
        p = Process(target=wrapper, args=(q, *args))
        p.start()
        p.join(timeout)

        if p.is_alive():
            print(f"⚠ Timeout atteint pour {func.__name__} après {timeout} secondes")
            p.terminate()
            p.join()
            return fallback

        if not q.empty():
            result = q.get()
            if isinstance(result, Exception):
                print(f"❌ Exception dans {func.__name__} : {result}")
                return fallback
            return result

        return fallback

"""Die Rechnung am Mac (Wirt: Bildwerk): Apple Vision über PyObjC. Vision misst Rahmen in Anteilen mit dem Ursprung unten
links; hier wird daraus oben links (`aus_vision`). Das Bild wird so gelesen, wie es angezeigt wird (Ausrichtung aus den
Bilddaten), damit die Rahmen auf das Bild passen, das die App zeigt. Ohne Netz, ohne Modell zum Laden."""

from __future__ import annotations

import time

from .modelle import Code, Erkannt, Erkennen, Gesicht, Rahmen, Textstelle


class BildFehler(Exception):
    """Das Bild ist nicht lesbar oder leer: kommt beim Aufrufer als 422 mit dem Grundwort `bild_fehler` an."""


def aus_vision(x: float, y: float, b: float, h: float) -> Rahmen:
    """Ein Rahmen von Vision (Ursprung unten links) in Anteilen von oben links, in die Grenzen des Bildes gelegt."""
    x0, y0 = max(0.0, min(1.0, x)), max(0.0, min(1.0, 1.0 - y - h))
    return Rahmen(x=x0, y=y0, b=max(0.0, min(1.0 - x0, b)), h=max(0.0, min(1.0 - y0, h)))


class ErkennenHier:
    """Rechnet mit Apple Vision; nur am Mac nutzbar (PyObjC: pyobjc-framework-Vision und -Quartz)."""

    def bereit(self) -> str:
        import Quartz  # noqa: F401
        import Vision
        return f"Apple Vision (Texterkennung Revision {Vision.VNRecognizeTextRequestRevision3})"

    def erkennen(self, inhalt: bytes, auftrag: Erkennen) -> Erkannt:
        import Quartz
        import Vision
        from Foundation import NSData

        ab = time.perf_counter()
        quelle = Quartz.CGImageSourceCreateWithData(NSData.dataWithBytes_length_(inhalt, len(inhalt)), None)
        bild = Quartz.CGImageSourceCreateImageAtIndex(quelle, 0, None) if quelle is not None else None
        if bild is None:
            raise BildFehler("Das Bild lässt sich nicht lesen")
        eigenschaften = Quartz.CGImageSourceCopyPropertiesAtIndex(quelle, 0, None) or {}
        ausrichtung = int(eigenschaften.get(Quartz.kCGImagePropertyOrientation, 1) or 1)
        w, h = Quartz.CGImageGetWidth(bild), Quartz.CGImageGetHeight(bild)
        if ausrichtung in (5, 6, 7, 8):          # um 90 Grad gedreht: so breit und hoch, wie es angezeigt wird
            w, h = h, w
        anfragen = []
        text = gesichter = codes = None
        if auftrag.texte:
            text = Vision.VNRecognizeTextRequest.alloc().init()
            text.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate if auftrag.genau else Vision.VNRequestTextRecognitionLevelFast)
            text.setRecognitionLanguages_(auftrag.sprachen)
            text.setUsesLanguageCorrection_(True)
            anfragen.append(text)
        if auftrag.gesichter:
            gesichter = Vision.VNDetectFaceRectanglesRequest.alloc().init()
            anfragen.append(gesichter)
        if auftrag.codes:
            codes = Vision.VNDetectBarcodesRequest.alloc().init()
            anfragen.append(codes)
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_orientation_options_(bild, ausrichtung, None)
        ok, fehler = handler.performRequests_error_(anfragen, None)
        if not ok:
            raise BildFehler(f"Apple Vision: {fehler.localizedDescription() if fehler else 'unbekannter Fehler'}")
        texte = []
        for beob in (text.results() or []) if text is not None else []:
            kandidat = beob.topCandidates_(1)
            if not kandidat:
                continue
            r = beob.boundingBox()
            texte.append(Textstelle(text=str(kandidat[0].string()), rahmen=aus_vision(r.origin.x, r.origin.y, r.size.width, r.size.height),
                                    sicherheit=max(0.0, min(1.0, float(kandidat[0].confidence())))))
        gefunden = []
        for beob in (gesichter.results() or []) if gesichter is not None else []:
            r = beob.boundingBox()
            gefunden.append(Gesicht(rahmen=aus_vision(r.origin.x, r.origin.y, r.size.width, r.size.height), sicherheit=max(0.0, min(1.0, float(beob.confidence())))))
        strich = []
        for beob in (codes.results() or []) if codes is not None else []:
            r = beob.boundingBox()
            art = str(beob.symbology() or "").removeprefix("VNBarcodeSymbology")
            strich.append(Code(art=art, inhalt=str(beob.payloadStringValue() or ""), rahmen=aus_vision(r.origin.x, r.origin.y, r.size.width, r.size.height),
                               sicherheit=max(0.0, min(1.0, float(beob.confidence())))))
        return Erkannt(breite=int(w), hoehe=int(h), texte=texte, gesichter=gefunden, codes=strich, ms=(time.perf_counter() - ab) * 1000)

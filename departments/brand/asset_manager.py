"""Asset Manager — custodia logos, plantillas, paletas y tipografías (tesis §6.4, rol nuevo).

Brand v1.0 custodia y responde con la versión vigente y sus metadatos; NO diseña assets
nuevos —eso queda fuera de la primera versión. Lee el manifiesto declarativo de
`empresas/<empresa>/brand/assets_manifest.json`.
"""
from __future__ import annotations

from departments.brand import config as brand_cfg


class AssetManager:
    def __init__(self, empresa: str = "laboratorio") -> None:
        self.empresa = empresa
        self.manifest = brand_cfg.cargar_assets(empresa)

    def paleta(self) -> dict:
        return dict(self.manifest.get("paleta", {}))

    def tipografias(self) -> dict:
        return dict(self.manifest.get("tipografias", {}))

    def logo(self, logo_id: str = "logo_principal") -> dict | None:
        for l in self.manifest.get("logos", []):
            if l.get("id") == logo_id:
                return dict(l)
        return None

    def plantilla(self, plantilla_id: str) -> dict | None:
        for p in self.manifest.get("plantillas", []):
            if p.get("id") == plantilla_id:
                return dict(p)
        return None

    def vigente(self) -> dict:
        """Versión vigente del set de marca, con metadatos para auditar consistencia."""
        return {
            "version": self.manifest.get("version", "0"),
            "actualizado": self.manifest.get("actualizado", ""),
            "paleta": self.paleta(),
            "tipografias": self.tipografias(),
            "n_logos": len(self.manifest.get("logos", [])),
            "n_plantillas": len(self.manifest.get("plantillas", [])),
        }

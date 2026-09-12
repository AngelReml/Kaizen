"""Departamento Comercial Sintético — Fase 0+ del v0.2.

Esta carpeta implementa el plano `Kaizen_DepartamentoComercial_v0.2.docx`:
- Roles (Director, Researcher, Enrichment, SDR, Account Executive…) en sus propios módulos.
- Datos del ICP en `datos/icp_<empresa>.json` (editable sin tocar código).
- Distancias logísticas reales vía `distancia/` (Google Routes con fallback haversine).
- Anillos geográficos del §5.4.
- Lifecycle del lead (§3) con persistencia inmutable de transiciones.
- Métricas verde/ámbar/rojo del §7.1.
- Reporte ejecutivo del viernes (§7.4).

Ver `docs/PLAN_DEPARTAMENTO_COMERCIAL.md` para el plan completo de construcción por fases.
"""

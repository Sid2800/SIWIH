---
description: "Auditoría de regresión del frontend en SG-transporte_hospitalario"
name: "Auditoría de Regresión Frontend"
agent: "agent"
argument-hint: "Audita la regresión frontend del módulo y documenta hallazgos"
---

Audita el frontend del módulo SG-transporte_hospitalario para detectar regresiones, sin modificar código y sin proponer soluciones todavía.

## Objetivo

Identificar exactamente qué se perdió, qué se sobrescribió y en qué capa deja de renderizar el flujo actual.

## Alcance

Revisa, como mínimo:
- [sg_transporte_hospitalario/templates/sg_transporte_hospitalario/dashboard.html](../../sg_transporte_hospitalario/templates/sg_transporte_hospitalario/dashboard.html)
- [core/static/core/scripts/sg_transporte_hospitalario/dashboard/dashboard.js](../../core/static/core/scripts/sg_transporte_hospitalario/dashboard/dashboard.js)
- [core/static/core/css/sg_transporte_hospitalario/dashboard/dashboard.css](../../core/static/core/css/sg_transporte_hospitalario/dashboard/dashboard.css)
- Las vistas, contextos y endpoints que alimentan el dashboard.

## Qué debes verificar

- Estructura del dashboard y de sus pestañas.
- Componentes eliminados o sobrescritos.
- Funciones que dejaron de ejecutarse.
- Inicializaciones perdidas o duplicadas.
- Errores de render, integración o consola.
- IDs HTML, clases CSS, data-attributes, listeners, endpoints y llamadas AJAX.
- Flujo completo desde backend -> JSON -> JavaScript -> HTML -> CSS.

## Instrucciones de análisis

- No cambies archivos.
- No implementes correcciones.
- No propongas refactorizaciones.
- Clasifica cada hallazgo como Crítico, Medio o Menor.
- Indica archivo, función o componente involucrado y la causa probable.
- Si una parte del frontend dejó de renderizar, especifica la capa exacta donde se rompe.
- Si encuentras componentes equivalentes renombrados, indícalos claramente.

## Resultado esperado

Entrega un documento técnico con esta estructura:
- Resumen ejecutivo.
- Estado de Autorización.
- Estado de Construcción del Viaje.
- Componentes perdidos.
- Componentes sobrescritos.
- Componentes no inicializados.
- Componentes con render roto.
- Funciones afectadas.
- Archivos afectados.
- Causa raíz probable.
- Recomendaciones de recuperación.

## Criterio de salida

Escribe el informe con evidencia concreta del estado actual del workspace y del navegador si está disponible. Si faltan datos, dilo explícitamente.
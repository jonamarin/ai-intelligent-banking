<!--
SYNTHETIC / TEAM-AUTHORED — not a real bank's policy. See dispute_policy.md
header for context.
-->

# Política de Bloqueo de Tarjeta (SYNTHETIC)

El bloqueo de una tarjeta es una acción de alto riesgo (`docs/decision-policy.md` § 6) porque
afecta directamente la capacidad del cliente de usar su cuenta. Requiere autorización más
fuerte que una simple recomendación del sistema de IA.

Un bloqueo puede recomendarse cuando la evidencia respalda fraude de forma consistente y sin
contradicciones significativas. Cuando existen contradicciones en la evidencia (por ejemplo,
un dispositivo conocido pero un país nuevo), el caso debe escalarse a un analista humano antes
de bloquear la tarjeta, en lugar de bloquear automáticamente.

El bloqueo nunca debe ejecutarse basándose únicamente en la confianza del modelo de IA — la
confianza del modelo no es autorización (`docs/decision-policy.md` § 2).

<!--
SYNTHETIC / TEAM-AUTHORED — not a real bank's policy. Written for this
project's RAG demonstration (docs/architecture.md § 7, prompt.md § 18).
Never present this as an approved institutional policy.
-->

# Política de Disputas de Transacciones (SYNTHETIC)

Cuando un cliente reporta una transacción que no reconoce, el sistema debe reunir evidencia
antes de tomar cualquier acción. Una disputa puede crearse cuando existe evidencia razonable
de que la transacción no fue autorizada por el titular de la cuenta.

La creación de una disputa es una acción de riesgo medio (`docs/decision-policy.md` § 6): puede
automatizarse solo cuando la política lo permite explícitamente para el nivel de riesgo del
caso. Una disputa nunca debe crearse basándose únicamente en la afirmación del cliente sin
evidencia de respaldo — pero tampoco debe negarse automáticamente sin evidencia en contra.

Toda disputa creada debe quedar vinculada al caso, a la evidencia que la respalda, y a la
versión de política vigente en el momento de la decisión.

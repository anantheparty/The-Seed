

# The Seed – Un framework de agentes LLM para desarrolladores de juegos

[中文版README](https://github.com/anantheparty/The-Seed/blob/main/README_CN.md)

## Descripción general

**The Seed** es un framework de código abierto diseñado para desarrolladores de juegos. Sus objetivos son:

- Permitir que los juegos expongan su **estado / acciones** a un Agente-LLM a través de un protocolo de integración unificado, lo que permite al LLM observar el juego, emitir acciones e interactuar con los jugadores.

- Permitir que los LLM y la IA tradicional de videojuegos formen un flujo de trabajo complementario, manejando la toma de decisiones y la ejecución juntos bajo un presupuesto de computación controlado.

---

## Principios de diseño

1. **Otorgar al Agente un punto de entrada claro y bien definido**

   - La suposición básica es que el juego está dispuesto a exponer una capa de interfaz de “observaciones / acciones / eventos”.
   - La integración debe ser mínimamente invasiva, más parecido a adjuntar un módulo que a reescribir la lógica del juego.
   - El framework busca mantenerse compatible con diferentes arquitecturas de motores y permitir una integración ligera y mantenible.

2. **LLM para decisiones de alto nivel, juego para la ejecución**

   - Los LLM sobresalen en: comprensión situacional, generación de planes, razonamiento estratégico y explicación de comportamientos.
   - La IA nativa del juego (árboles de comportamiento / máquinas de estados / sistemas de reglas) sobresale en: búsqueda de rutas, micro-acciones, verificación de condiciones y lógica a nivel de fotograma.
   - The Seed sigue esta separación de roles:  
     **El LLM genera intenciones → el juego las ejecuta.**  
     Lograr un comportamiento estable con llamadas mínimas al modelo.

3. **No está vinculado a un gameplay específico**

   - Proporciona un protocolo extensible de Acción / Observación / Herramienta.
   - No predefine semánticas como “atacar / recolectar / construir”; cada juego define sus propias acciones y estructuras de datos.
   - El framework organiza estas definiciones en prompts e interfaces de herramientas amigables para el LLM, para que diferentes juegos puedan construir sus propios estilos de Agente dentro de un framework compartido.

4. **Iterar a partir de la experiencia real de integración**

   - El proyecto aún está en desarrollo activo.
   - Prioridad: reducir los pasos y el código necesarios para que un nuevo juego pueda “pasar de cero a tener un Agente en funcionamiento”.
   - Utilizar proyectos reales para refinar los andamios, ejemplos, herramientas de depuración y las mejores prácticas.
   - El objetivo a largo plazo es proporcionar un framework que sea **práctico, bien documentado y fácil de introducir en tu equipo.**

---

## Estado actual del proyecto

- **Etapa: PoC / Prototipo inicial**
  - ✅ Completado: borrador de la arquitectura general y flujo de trabajo de interacción del agente
  - ✅ Completado: versión inicial de la API del lado del juego (observación / acción / evento)
  - ⏳ En progreso:  
    - Protocolo central de Agente de The Seed  
    - Agente Demo para OpenRA (por ejemplo, auto-econ / auto-battle)  
    - Primera versión de README / documentación / guías de integración

---

## Hoja de ruta

### Fase 0 – Validación con OpenRA (⏳ En curso, ~45–60 días)

- Definir un protocolo básico de Agente orientado a RTS (observación / acción / tick / evento)
- Entregar una **“Demo OpenRA + Agente”** que funcione out-of-the-box
- Preparar documentación para desarrolladores:
  - Cómo integrar The Seed en un juego
  - Cómo escribir un Agente-LLM mínimo que controle una facción

### Fase 1 – Estabilización del framework y documentación

- Extraer un **SDK Central** desacoplado de cualquier juego específico
- Mejorar:
  - Gestión del ciclo de vida del agente
  - Tick / planificación / memoria / logging
  - Adaptadores para modelos LLM en la nube o locales

### Fase 2 – Integración multijuego y crecimiento de la comunidad

- Agregar un segundo juego soportado (prioridad: estrategia / simulación)
- Construir una **Colección de Integraciones de Ejemplo**
- Organizar actividades orientadas a desarrolladores:
  - Hackathon / Game Jam
  - Talleres en línea y compartir conocimiento técnico

### Fase 3 – Ecosistema de Agentes

- Proponer un **Estándar de Descripción de Agentes** para soportar:
  - Compartir estrategias entre diferentes juegos  
  - Roles de Agentes creados por la comunidad
- Explorar características adicionales:
  - Cooperación Multi-Agente
  - Agentes tipo entrenador / espectador
  - Agentes de análisis / explicación de replays

---

## Cómo contribuir

- ⭐ **Star the repo** — sigue las actualizaciones y apoya al proyecto  
- 🐛 **Open Issues** — ideas, retroalimentación, reportes de errores  
- 🔧 **Submit PRs** — documentación, mejoras, ejemplos  
- 📣 **Spread the word** — comparte con desarrolladores de juegos o entusiastas de la IA

---

## Primeros pasos

TODO

### 1. Configuración del entorno

TODO

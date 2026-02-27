# Plan de Implementación y Validaciones: Extensión Híbrida para Nova

Este documento define los pasos a seguir para implementar la recomendación de usar la librería oficial `deepagents` adaptándola para Amazon Nova, incorporando tus herramientas de investigación locales y tus barreras de contención neurodivergentes.

## Fase 1: Preparación del Entorno

### Paso 1.1: Instalar Dependencias

Instalar la versión oficial de `deepagents` en el entorno virtual del proyecto (asegurando compatibilidad con LangChain 1.0.0+).

**Validación:**

1. Ejecutar `pip show deepagents` y verificar la instalación.
2. Abrir un REPL de Python y comprobar que se importan los paquetes:

   ```python
   from deepagents import create_deep_agent
   from deepagents.middleware.filesystem import FilesystemMiddleware
   from deepagents.middleware.subagents import SubAgentMiddleware
   from deepagents.middleware.summarization import SummarizationMiddleware
   from langchain.agents.middleware import TodoListMiddleware
   ```

   **Criterio de éxito:** Las importaciones funcionan sin `ModuleNotFoundError`.

---

## Fase 2: Configuración del Stack de Middleware para Nova

### Paso 2.1: Determinar el "Happy Path" del Modelo Nova

Amazon NovaLite/NovaPro tiene diferentes comportamientos de tool-calling en comparación con Claude.
Hay que configurar el `create_deep_agent` inyectando un stack explícito que omita los middlewares de Anthropic.

**Acciones:**
Crear un archivo `src/neuro_agent/infrastructure/factory.py` con una fábrica de agentes:

```python
from langchain_aws import ChatBedrockConverse
from deepagents import create_deep_agent
# Import tools
from neuro_agent.infrastructure.tools.research import tavily_search, think_tool

def build_nova_agent(checkpointer=None, system_prompt=None):
    model = ChatBedrockConverse(model="us.amazon.nova-pro-v1:0", region_name="us-east-1")
    
    # IMPORTANTE: Definir el middleware SIN AnthropicPromptCaching ni PatchToolCalls
    middleware_stack = [
        # 1. Langchain default
        TodoListMiddleware(),
        # 2. DeepAgents
        FilesystemMiddleware(),
        # IMPORTANTE: No añadimos SubAgentMiddleware globalmente aquí 
        # para probar primero el núcleo de Nova
    ]
    
    # 3. Añadir el NeuroGuardrails personalizado que creaste
    from neuro_agent.infrastructure.neuro_guardrails import NeuroGuardrailsMiddleware
    middleware_stack.append(NeuroGuardrailsMiddleware())
    
    return create_deep_agent(
        model=model,
        tools=[tavily_search, think_tool],
        middleware=middleware_stack,
        system_prompt=system_prompt,
        checkpointer=checkpointer
    )
```

**Validación:**
Instanciar la fábrica con `build_nova_agent()` en un script de prueba y comprobar el tipo devuelto.
**Criterio de éxito:** Retorna un objeto `CompiledStateGraph`.

---

## Fase 3: Pruebas Elementales de Middleware

### Paso 3.1: Validar el TodoListMiddleware nativo

Ejecutar un script enviando al agente una petición multicapa.

**Prueba:** "Investiga sobre LangGraph y luego haz un resumen, escríbelo en resumen_langgraph.md".
**Validaciones:**

1. **Inspección de Estado:** El campo `todos` del `State` debe llenarse con una lista planificada *antes* de que ocurran las búsquedas o la escritura del archivo.
2. **Ciclo de Ejecución:** Verificar en LangSmith (o en consola) que el modelo primero hace una llamada a `write_todos` antes de llamar a `tavily_search`.
**Criterio de éxito:** El agente crea un plan usando `write_todos` primero, luego lo ejecuta.

### Paso 3.2: Validar la Ejecución Rápida y Escape Valve

Se debe probar forzar al agente a saltarse las reglas para ver si el `NeuroGuardrailsMiddleware` y el enforcing del Todo entran en acción, pero logran escapar en máximo 3 reintentos.

**Prueba:** Mandar un system prompt hostil pidiéndole al modelo que responda sin pensar y sin herramientas.
**Validaciones:**

1. Ver en los `messages` del estado si aparecen inyecciones con "⛔ SYSTEM GUARD:".
2. Confirmar que no ocurre un bucle infinito (se debe detener en `MAX_GUARD_RETRIES`).
**Criterio de éxito:** El agente se bloquea y retrocede al modelo, o en el peor de los casos abandona tras 3 intentos, pero no entra en recursión de iteración > 1000.

---

## Fase 4: Reducción del System Prompt

### Paso 4.1: Optimizar Prompts

Los prompts largos ahogan el contexto y confunden a Nova.
Crear en `src/neuro_agent/infrastructure/prompts_nova.py` unas instrucciones limitadas a la metodología.

Eliminar completamente del prompt:

1. Instrucciones sobre cómo forzar `write_todos` (el middleware de langchain se encarga).
2. Tanta verbosidad sobre fallos.

**Prueba:** Proveer el nuevo prompt a `build_nova_agent(system_prompt=NEW_PROMPT)`.
**Validación empírica:** Comparar el costo de invocación inicial (input tokens) usando el prompt de Sonnet (1000+ words) vs el nuevo de Nova (~300 words).
**Criterio de éxito:** Reducción de tokens de sistema superior al 60%, sin pérdida de disciplina en los logs de ejecución.

---

## Fase 5: Activación de Sub-agentes y Memoria

### Paso 5.1: Integrar SubAgentMiddleware

Una vez estable el loop base, añadir delegación de tareas.

**Acciones:**
Integrar a la lista de middlewares el `SubAgentMiddleware`. Hay que configurar a mano la especificidad para sub-agentes compatibles con Nova, asegurando que cada sub-agente tenga un `ChatBedrockConverse` en lugar del predeterminado de DeepAgents (que invocaría la API de Anthropic por defecto si no le pasamos nuestra configuración).

**Prueba:** Pedirle investigar dos temas en paralelo ("Investiga A, y a la vez investiga B").
**Validación:**

1. Verificar que el agente utiliza la herramienta `task` (provista por `SubAgentMiddleware`) al menos dos veces.
2. Comprobar que esto no levanta excepciones de tipo de serialización de LangChain para AWS Bedrock.
**Criterio de éxito:** Finalización con un resumen combinado desde las lecturas de los archivos de cada sub-agente.

---

## Retrospectiva Final

Validar contra la principal hipótesis del análisis:
¿Pasa la arquitectura híbrida el flujo más limpiamente y previene los Infinite Loops mientras soporta los neuro_guardrails?

Si la prueba de la fase 5 se completa correctamente con `recursion_limit` sobrante (ejecutándose en 10-25 pasos en lugar de caer en fallos), el rediseño es exitoso.

"""Frontend Agent - generates React + Tailwind frontend code.

Produces:
- main.tsx / App.tsx entry points
- Component files for each feature
- API service layer
- Basic styling
"""

import json
from typing import List

from app.core.logging import get_logger
from app.agents.base import Agent, PlanStep
from app.agents.types import AgentRole, Artifact, Context, Plan

logger = get_logger(__name__)


class FrontendAgent(Agent):
    """Frontend Agent - generates React + Tailwind code."""

    role = AgentRole.FRONTEND
    description = "Generate React + TypeScript + Tailwind CSS frontend code"

    def _default_plan_summary(self, ctx: Context) -> str:
        return "Generate React frontend components, pages, and API client"

    def _default_plan_steps(self, ctx: Context) -> List[PlanStep]:
        return [
            PlanStep(description="Create App component and routing", tool="file_write"),
            PlanStep(description="Create API service layer", tool="file_write"),
            PlanStep(description="Create main pages and components", tool="file_write"),
            PlanStep(description="Add styles and polish", tool="file_write"),
        ]

    async def execute(self, plan: Plan, ctx: Context) -> Artifact:
        """Generate frontend code based on PRD/design."""
        logger.info("frontend_agent_execute", session_id=ctx.session_id)

        requirement = ctx.user_requirement

        # Get features from design or requirements agent
        features = self._extract_features(ctx)

        # Generate all frontend files
        app_tsx = self._generate_app_tsx(features)
        api_ts = self._generate_api_ts(features)
        pages_tsx = self._generate_pages(features)
        main_tsx = self._generate_main_tsx()
        index_css = self._generate_index_css()

        # Combine into a single artifact (multiple files represented in content)
        content_parts = []
        for name, code in [
            ("frontend/src/main.tsx", main_tsx),
            ("frontend/src/App.tsx", app_tsx),
            ("frontend/src/api.ts", api_ts),
            ("frontend/src/pages.tsx", pages_tsx),
            ("frontend/src/index.css", index_css),
        ]:
            content_parts.append(f"--- {name} ---\n\n{code}\n\n")

        combined = "\n".join(content_parts)

        artifact = Artifact(
            agent_role=self.role.value,
            artifact_type="code",
            name="frontend_code",
            content=combined,
            metadata={
                "files_generated": 5,
                "features": [f["title"] for f in features],
                "files": [
                    {"path": "frontend/src/main.tsx", "content": main_tsx},
                    {"path": "frontend/src/App.tsx", "content": app_tsx},
                    {"path": "frontend/src/api.ts", "content": api_ts},
                    {"path": "frontend/src/pages.tsx", "content": pages_tsx},
                    {"path": "frontend/src/index.css", "content": index_css},
                ],
            },
        )

        logger.info("frontend_agent_done", session_id=ctx.session_id)
        return artifact

    def _extract_features(self, ctx: Context) -> List[dict]:
        """Extract features from context (PRD or design agent)."""
        # Try design agent first
        design_output = ctx.get_output(AgentRole.DESIGN.value)
        if design_output and hasattr(design_output, "metadata"):
            features_meta = design_output.metadata.get("features")
            if features_meta:
                return [{"title": f, "description": f"Manage {f}"} for f in features_meta]

        # Fall back to requirements agent
        req_output = ctx.get_output(AgentRole.REQUIREMENTS.value)
        if req_output and hasattr(req_output, "metadata"):
            return req_output.metadata.get("features", [])

        return [{"title": "items", "description": "Core items management"}]

    def _generate_main_tsx(self) -> str:
        """Generate main.tsx entry point."""
        return '''import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
'''

    def _generate_app_tsx(self, features: List[dict]) -> str:
        """Generate App.tsx with routing."""
        route_lines = []
        nav_links = []
        for feature in features:
            title = feature["title"]
            slug = title.lower().replace(" ", "-")
            component_name = title.replace(" ", "")
            route_lines.append(
                f'          <Route path="/{slug}" element={{<{component_name}Page />}} />'
            )
            nav_links.append(
                f'          <NavLink to="/{slug}" className={{{{ isActive }}}} => isActive ? "text-blue-600 font-bold" : "text-gray-700 dark:text-gray-200">{title}</NavLink>'
            )

        routes_str = "\n".join(route_lines)
        nav_str = "\n".join(nav_links)
        import_names = ", ".join(
            [f["title"].replace(" ", "") + "Page" for f in features]
        )

        return (
            "import { Routes, Route, NavLink } from 'react-router-dom'\n"
            f"import {{ HomePage, {import_names} }} from './pages'\n"
            "\n"
            "function App() {\n"
            "  return (\n"
            '    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">\n'
            '      <nav className="bg-white dark:bg-gray-800 shadow px-6 py-4">\n'
            '        <div className="flex items-center gap-6">\n'
            '          <NavLink to="/" className={({ isActive }) => isActive ? "text-blue-600 font-bold" : "text-gray-700 dark:text-gray-200"}>Home</NavLink>\n'
            f"{nav_str}\n"
            "        </div>\n"
            "      </nav>\n"
            '      <main className="max-w-6xl mx-auto px-6 py-8">\n'
            "        <Routes>\n"
            '          <Route path="/" element={<HomePage />} />\n'
            f"{routes_str}\n"
            "        </Routes>\n"
            "      </main>\n"
            "    </div>\n"
            "  )\n"
            "}\n"
            "\n"
            "export default App\n"
        )

    def _generate_api_ts(self, features: List[dict]) -> str:
        """Generate API service layer."""
        fn_codes = []
        for feature in features:
            title = feature["title"]
            resource = title.lower().replace(" ", "_")
            fn_name = title.replace(" ", "").capitalize()

            lines = []
            lines.append("// " + title + " API")
            lines.append(f"export interface {fn_name}Item {{")
            lines.append("  id: number;")
            lines.append("  title: string;")
            lines.append("  description?: string;")
            lines.append("  status: string;")
            lines.append("  created_at: string;")
            lines.append("  updated_at: string;")
            lines.append("}")
            lines.append("")
            lines.append(
                f"export async function fetch{fn_name}List(): Promise<{fn_name}Item[]> {{"
            )
            lines.append(f"  const res = await fetch(`/api/v1/{resource}`);")
            lines.append(f"  if (!res.ok) throw new Error(`Failed to fetch {resource}`);")
            lines.append("  const data = await res.json();")
            lines.append("  return data.success ? data.data : [];")
            lines.append("}")
            lines.append("")
            lines.append(
                f"export async function create{fn_name}(item: {{ title: string; description?: string }}): Promise<{fn_name}Item> {{"
            )
            lines.append(f"  const res = await fetch(`/api/v1/{resource}`, {{")
            lines.append("    method: 'POST',")
            lines.append("    headers: {{ 'Content-Type': 'application/json' }},")
            lines.append("    body: JSON.stringify(item),")
            lines.append("  });")
            lines.append(f"  if (!res.ok) throw new Error(`Failed to create {resource}`);")
            lines.append("  const data = await res.json();")
            lines.append("  return data.success ? data.data : null;")
            lines.append("}")
            lines.append("")
            lines.append(
                f"export async function update{fn_name}(id: number, item: {{ title?: string; status?: string }}): Promise<{fn_name}Item> {{"
            )
            lines.append(f"  const res = await fetch(`/api/v1/{resource}/` + id, {{")
            lines.append("    method: 'PUT',")
            lines.append("    headers: {{ 'Content-Type': 'application/json' }},")
            lines.append("    body: JSON.stringify(item),")
            lines.append("  });")
            lines.append(f"  if (!res.ok) throw new Error(`Failed to update {resource}`);")
            lines.append("  const data = await res.json();")
            lines.append("  return data.success ? data.data : null;")
            lines.append("}")
            lines.append("")
            lines.append(
                f"export async function delete{fn_name}(id: number): Promise<boolean> {{"
            )
            lines.append(f"  const res = await fetch(`/api/v1/{resource}/` + id, {{ method: 'DELETE' }});")
            lines.append("  return res.ok;")
            lines.append("}")
            fn_codes.append("\n".join(lines))
        return "\n\n".join(fn_codes)

    def _generate_pages(self, features: List[dict]) -> str:
        """Generate page components for each feature."""
        pages = []

        home_page = (
            "// Home page\n"
            "export function HomePage() {\n"
            "  return (\n"
            '    <div className="space-y-6">\n'
            '      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow">\n'
            '        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">Welcome</h1>\n'
            '        <p className="text-gray-600 dark:text-gray-400">Select a feature from the navigation to get started.</p>\n'
            "      </div>\n"
            "    </div>\n"
            "  )\n"
            "}\n"
        )
        pages.append(home_page)

        # Feature pages
        for feature in features:
            title = feature["title"]
            description = feature.get("description", "")
            name = title.replace(" ", "")
            resource = title.lower().replace(" ", "_")
            cap = name.capitalize()

            page = (
                f"// {title} page\n"
                "import { useEffect, useState } from 'react';\n"
                f"import {{ fetch{cap}List, create{cap}, update{cap}, delete{cap} }} from './api';\n"
                "\n"
                f"export function {cap}Page() {{\n"
                "  const [items, setItems] = useState<any[]>([]);\n"
                "  const [newTitle, setNewTitle] = useState('');\n"
                "  const [loading, setLoading] = useState(false);\n"
                "\n"
                "  useEffect(() => {\n"
                "    loadItems();\n"
                "  }, []);\n"
                "\n"
                "  async function loadItems() {\n"
                "    setLoading(true);\n"
                "    try {\n"
                f"      const data = await fetch{cap}List();\n"
                "      setItems(data);\n"
                "    } finally {\n"
                "      setLoading(false);\n"
                "    }\n"
                "  }\n"
                "\n"
                "  async function handleCreate(e: React.FormEvent) {\n"
                "    e.preventDefault();\n"
                "    if (!newTitle.trim()) return;\n"
                f"    await create{cap}({{ title: newTitle }});\n"
                "    setNewTitle('');\n"
                "    loadItems();\n"
                "  }\n"
                "\n"
                "  async function handleDelete(id: number) {\n"
                f"    await delete{cap}(id);\n"
                "    loadItems();\n"
                "  }\n"
                "\n"
                "  async function handleToggleStatus(item: any) {\n"
                "    const newStatus = item.status === 'active' ? 'inactive' : 'active';\n"
                f"    await update{cap}(item.id, {{ status: newStatus }});\n"
                "    loadItems();\n"
                "  }\n"
                "\n"
                "  return (\n"
                '    <div className="space-y-6">\n'
                '      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow">\n'
                f'        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{title}</h1>\n'
                f'        <p className="text-gray-600 dark:text-gray-400 mt-2">{description}</p>\n'
                "      </div>\n"
                "\n"
                '      <form onSubmit={handleCreate} className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow">\n'
                '        <div className="flex gap-4">\n'
                "          <input\n"
                '            type="text"\n'
                '            value={newTitle}\n'
                '            onChange={(e) => setNewTitle(e.target.value)}\n'
                '            placeholder="Add a new item..."\n'
                '            className="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 px-4 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"\n'
                "          />\n"
                "          <button\n"
                '            type="submit"\n'
                '            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-500"\n'
                "          >\n"
                "            Add\n"
                "          </button>\n"
                "        </div>\n"
                "      </form>\n"
                "\n"
                '      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow">\n'
                "        {loading ? (\n"
                '          <p className="text-gray-500">Loading...</p>\n'
                "        ) : items.length === 0 ? (\n"
                '          <p className="text-gray-500">No items yet. Create your first one!</p>\n'
                "        ) : (\n"
                '          <ul className="space-y-3">\n'
                "            {items.map((item) => (\n"
                '              <li key={item.id} className="flex items-center justify-between border-b border-gray-200 dark:border-gray-700 pb-3">\n'
                "                <div>\n"
                '                  <p className="font-medium text-gray-900 dark:text-white">{item.title}</p>\n'
                '                  {item.description && <p className="text-sm text-gray-500">{item.description}</p>}\n'
                "                </div>\n"
                '                <div className="flex items-center gap-3">\n'
                "                  <button\n"
                "                    onClick={() => handleToggleStatus(item)}\n"
                '                    className="px-3 py-1 rounded-full text-sm bg-gray-100 text-gray-800 hover:bg-green-100 hover:text-green-800 transition-colors"\n'
                "                  >\n"
                "                    {item.status}\n"
                "                  </button>\n"
                "                  <button\n"
                "                    onClick={() => handleDelete(item.id)}\n"
                '                    className="text-red-600 hover:text-red-800 text-sm"\n'
                "                  >\n"
                "                    Delete\n"
                "                  </button>\n"
                "                </div>\n"
                "              </li>\n"
                "            ))}\n"
                "          </ul>\n"
                "        )}\n"
                "      </div>\n"
                "    </div>\n"
                "  );\n"
                "}\n"
            )
            pages.append(page)

        exports = ", ".join(
            [f["title"].replace(" ", "").capitalize() + "Page" for f in features]
        )
        return "\n\n".join(pages) + f"\n\nexport {{ HomePage, {exports} }};\n"

    def _generate_index_css(self) -> str:
        """Generate Tailwind entry CSS."""
        return '''@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
}

.active {
  color: rgb(14, 165, 233);
  font-weight: 600;
}
'''

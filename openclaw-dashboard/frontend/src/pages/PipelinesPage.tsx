import { useEffect, useState, useCallback } from 'react';
import {
  FolderOpen, File, FileText, ChevronRight, ChevronDown, X,
  LayoutGrid, Columns2, Columns3, Columns4,
} from 'lucide-react';
import { AGENTS } from '../constants/agents';
import { fetchProjects, fetchProjectTree, fetchProjectFile } from '../api/endpoints';
import type { ProjectInfo, FileNode } from '../api/types';
import EmptyState from '../components/common/EmptyState';

const columnIcons = [LayoutGrid, Columns2, Columns3, Columns4];

function getStoredColumns(): number {
  try {
    const v = localStorage.getItem('pipelines-columns');
    if (v) {
      const n = parseInt(v, 10);
      if (n >= 1 && n <= 4) return n;
    }
  } catch {}
  return 2;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string | null): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return '';
  }
}

// Lightweight markdown renderer
function renderMarkdown(src: string): string {
  const lines = src.split('\n');
  const out: string[] = [];
  let inCode = false;
  let inList = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Fenced code blocks
    if (line.startsWith('```')) {
      if (inCode) {
        out.push('</code></pre>');
        inCode = false;
      } else {
        if (inList) { out.push('</ul>'); inList = false; }
        out.push('<pre class="bg-slate-900 rounded-lg p-3 my-2 overflow-x-auto text-sm"><code>');
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      out.push(escapeHtml(line));
      out.push('\n');
      continue;
    }

    // Blank line
    if (line.trim() === '') {
      if (inList) { out.push('</ul>'); inList = false; }
      continue;
    }

    // Headers
    const hMatch = line.match(/^(#{1,3})\s+(.+)/);
    if (hMatch) {
      if (inList) { out.push('</ul>'); inList = false; }
      const level = hMatch[1].length;
      const sizes = ['text-lg font-bold', 'text-base font-semibold', 'text-sm font-medium'];
      out.push(`<h${level} class="${sizes[level - 1]} text-white mt-4 mb-2">${inlineMarkdown(hMatch[2])}</h${level}>`);
      continue;
    }

    // List items
    if (line.match(/^\s*[-*]\s+/)) {
      if (!inList) { out.push('<ul class="list-disc list-inside space-y-1 my-2">'); inList = true; }
      out.push(`<li class="text-slate-300">${inlineMarkdown(line.replace(/^\s*[-*]\s+/, ''))}</li>`);
      continue;
    }

    // Regular paragraph
    if (inList) { out.push('</ul>'); inList = false; }
    out.push(`<p class="text-slate-300 my-1.5">${inlineMarkdown(line)}</p>`);
  }

  if (inCode) out.push('</code></pre>');
  if (inList) out.push('</ul>');
  return out.join('\n');
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function inlineMarkdown(text: string): string {
  let s = escapeHtml(text);
  // Bold
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>');
  // Italic
  s = s.replace(/\*(.+?)\*/g, '<em>$1</em>');
  // Inline code
  s = s.replace(/`([^`]+)`/g, '<code class="bg-slate-900 px-1.5 py-0.5 rounded text-sm text-blue-300">$1</code>');
  // Links
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-blue-400 underline" target="_blank" rel="noopener noreferrer">$1</a>');
  return s;
}

function TreeWithPaths({ tree, agentId, projectName, onFileClick, selectedPath }: {
  tree: FileNode;
  agentId: string;
  projectName: string;
  onFileClick: (path: string) => void;
  selectedPath: string | null;
}) {
  return (
    <div className="space-y-0">
      {tree.children?.map((child, i) => (
        <PathTreeNode key={i} node={child} parentPath={projectName} depth={0} agentId={agentId} onFileClick={onFileClick} selectedPath={selectedPath} />
      ))}
    </div>
  );
}

function PathTreeNode({ node, parentPath, depth, agentId, onFileClick, selectedPath }: {
  node: FileNode;
  parentPath: string;
  depth: number;
  agentId: string;
  onFileClick: (path: string) => void;
  selectedPath: string | null;
}) {
  const [expanded, setExpanded] = useState(false);
  const fullPath = `${parentPath}/${node.name}`;

  if (node.type === 'file') {
    const isMd = node.is_markdown;
    return (
      <button
        onClick={() => isMd && onFileClick(fullPath)}
        className={`flex items-center gap-2 w-full text-left py-1 px-2 rounded text-sm transition-colors ${
          isMd ? 'hover:bg-slate-700/50 cursor-pointer' : 'cursor-default opacity-70'
        } ${selectedPath === fullPath ? 'bg-slate-700/50 text-blue-400' : 'text-slate-300'}`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {isMd ? <FileText size={14} className="shrink-0 text-blue-400" /> : <File size={14} className="shrink-0 text-slate-500" />}
        <span className="truncate">{node.name}</span>
        {node.size != null && <span className="text-xs text-slate-500 ml-auto shrink-0">{formatSize(node.size)}</span>}
      </button>
    );
  }

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left py-1 px-2 rounded text-sm text-slate-200 hover:bg-slate-700/50 transition-colors"
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {expanded ? <ChevronDown size={14} className="shrink-0" /> : <ChevronRight size={14} className="shrink-0" />}
        <FolderOpen size={14} className="shrink-0 text-amber-400" />
        <span className="truncate">{node.name}</span>
      </button>
      {expanded && node.children?.map((child, i) => (
        <PathTreeNode key={i} node={child} parentPath={fullPath} depth={depth + 1} agentId={agentId} onFileClick={onFileClick} selectedPath={selectedPath} />
      ))}
    </div>
  );
}

export default function PipelinesPage() {
  const [columns, setColumns] = useState<number>(getStoredColumns);
  const [activeAgent, setActiveAgent] = useState(AGENTS[0].id);
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedProject, setExpandedProject] = useState<string | null>(null);
  const [tree, setTree] = useState<FileNode | null>(null);
  const [treeLoading, setTreeLoading] = useState(false);
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [previewName, setPreviewName] = useState<string>('');
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  const loadProjects = useCallback(async (agent: string) => {
    setLoading(true);
    setExpandedProject(null);
    setTree(null);
    setPreviewContent(null);
    setSelectedPath(null);
    try {
      const data = await fetchProjects(agent);
      setProjects(data.projects);
    } catch {
      setProjects([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadProjects(activeAgent); }, [activeAgent, loadProjects]);

  function handleColumnsChange(n: number) {
    setColumns(n);
    localStorage.setItem('pipelines-columns', String(n));
  }

  async function handleExpandProject(projectName: string) {
    if (expandedProject === projectName) {
      setExpandedProject(null);
      setTree(null);
      setPreviewContent(null);
      setSelectedPath(null);
      return;
    }
    setExpandedProject(projectName);
    setPreviewContent(null);
    setSelectedPath(null);
    setTreeLoading(true);
    try {
      const data = await fetchProjectTree(activeAgent, projectName);
      setTree(data);
    } catch {
      setTree(null);
    }
    setTreeLoading(false);
  }

  async function handleFileClick(filePath: string) {
    setSelectedPath(filePath);
    try {
      const data = await fetchProjectFile(activeAgent, filePath);
      if (data.content) {
        setPreviewContent(data.content);
        setPreviewName(data.name);
      }
    } catch {
      setPreviewContent(null);
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Projects</h1>
        <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1 border border-slate-700/50">
          {[1, 2, 3, 4].map((n) => {
            const Icon = columnIcons[n - 1];
            return (
              <button
                key={n}
                onClick={() => handleColumnsChange(n)}
                title={`${n} column${n > 1 ? 's' : ''}`}
                className={`p-1.5 rounded transition-colors ${
                  columns === n
                    ? 'bg-blue-600/20 text-blue-400'
                    : 'text-slate-500 hover:text-white'
                }`}
              >
                <Icon size={16} />
              </button>
            );
          })}
        </div>
      </div>

      {/* Agent toggle bar */}
      <div className="flex gap-2 flex-wrap">
        {AGENTS.map((agent) => (
          <button
            key={agent.id}
            onClick={() => setActiveAgent(agent.id)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
              activeAgent === agent.id
                ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                : 'bg-slate-800 text-slate-400 border border-slate-700/50 hover:text-white'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${agent.dot}`} />
            {agent.name}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="text-sm text-slate-500 text-center py-16">Loading projects...</div>
      ) : projects.length === 0 ? (
        <EmptyState
          message="No projects yet"
          description="This agent hasn't created any project folders yet. Projects will appear here as the agent organizes task outputs."
          icon={FolderOpen}
        />
      ) : (
        <>
          {/* Project cards grid */}
          <div
            className="gap-4"
            style={{ display: 'grid', gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
          >
            {projects.map((p) => (
              <button
                key={p.name}
                onClick={() => handleExpandProject(p.name)}
                className={`bg-slate-800/50 rounded-xl p-4 border text-left transition-colors ${
                  expandedProject === p.name
                    ? 'border-blue-500/50 bg-slate-800/80'
                    : 'border-slate-700/50 hover:border-slate-600'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
                    <FolderOpen size={20} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-white font-semibold truncate">{p.name}</h3>
                    <div className="flex items-center gap-3 text-xs text-slate-400 mt-0.5">
                      <span>{p.file_count} file{p.file_count !== 1 ? 's' : ''}</span>
                      {p.last_modified && <span>{formatDate(p.last_modified)}</span>}
                    </div>
                  </div>
                  <ChevronRight size={16} className={`text-slate-500 transition-transform ${expandedProject === p.name ? 'rotate-90' : ''}`} />
                </div>
              </button>
            ))}
          </div>

          {/* Expanded project view */}
          {expandedProject && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-700/50">
                <FolderOpen size={16} className="text-amber-400" />
                <span className="text-sm font-medium text-white">{expandedProject}</span>
                <button onClick={() => { setExpandedProject(null); setTree(null); setPreviewContent(null); setSelectedPath(null); }} className="ml-auto text-slate-400 hover:text-white p-1">
                  <X size={14} />
                </button>
              </div>
              {treeLoading ? (
                <div className="text-sm text-slate-500 text-center py-8">Loading file tree...</div>
              ) : !tree ? (
                <div className="text-sm text-slate-500 text-center py-8">Failed to load file tree</div>
              ) : (
                <div className="flex divide-x divide-slate-700/50" style={{ minHeight: '300px' }}>
                  {/* File tree */}
                  <div className={`overflow-y-auto py-2 ${previewContent ? 'w-1/4' : 'w-full'}`} style={{ maxHeight: '500px' }}>
                    <TreeWithPaths
                      tree={tree}
                      agentId={activeAgent}
                      projectName={expandedProject}
                      onFileClick={handleFileClick}
                      selectedPath={selectedPath}
                    />
                  </div>
                  {/* Preview pane */}
                  {previewContent && (
                    <div className="flex-1 overflow-y-auto p-4" style={{ maxHeight: '500px' }}>
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs text-slate-400 font-medium">{previewName}</span>
                        <button
                          onClick={() => { setPreviewContent(null); setSelectedPath(null); }}
                          className="text-slate-500 hover:text-white p-1"
                        >
                          <X size={12} />
                        </button>
                      </div>
                      <div
                        className="prose-custom"
                        dangerouslySetInnerHTML={{ __html: renderMarkdown(previewContent) }}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

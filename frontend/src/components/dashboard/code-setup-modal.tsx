import React, { useState, useEffect } from "react";
import {
    X,
    Terminal,
    Plus,
    Loader2,
    Copy,
    CheckCircle2,
    AlertCircle,
    Cpu,
    Info,
    ChevronDown,
    Wand2,
    FileCode
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { CommandPaletteSelect } from "@/components/ui/command-palette-select";
import { cn } from "@/lib/utils";
import { API_BASE_URL, frontendApi } from "@/lib/api";

interface CodeDetailed {
    pk: number;
    label: string;
    description: string | null;
    default_calc_job_plugin: string;
    remote_abspath: string;
    prepend_text: string | null;
    append_text: string | null;
    with_mpi: boolean;
    use_double_quotes: boolean;
}

interface CodeSetupModalProps {
    isOpen: boolean;
    onClose: () => void;
    computerLabel: string;
    onSuccess?: () => void;
}

export function CodeSetupModal({
    isOpen,
    onClose,
    computerLabel,
    onSuccess,
}: CodeSetupModalProps) {
    const [isLoading, setIsLoading] = useState(false);
    const [isFetchingTemplates, setIsFetchingTemplates] = useState(false);
    const [templates, setTemplates] = useState<CodeDetailed[]>([]);
    const [selectedTemplatePk, setSelectedTemplatePk] = useState<string>("none");
    const [yamlInput, setYamlInput] = useState("");
    const [showYamlInput, setShowYamlInput] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    const [formData, setFormData] = useState({
        label: "",
        description: "",
        default_calc_job_plugin: "",
        remote_abspath: "",
        prepend_text: "",
        append_text: "",
        with_mpi: true,
        use_double_quotes: false,
    });

    useEffect(() => {
        if (isOpen && computerLabel) {
            fetchTemplates();
            setFormData({
                label: "",
                description: "",
                default_calc_job_plugin: "",
                remote_abspath: "",
                prepend_text: "",
                append_text: "",
                with_mpi: true,
                use_double_quotes: false,
            });
            setSelectedTemplatePk("none");
            setYamlInput("");
            setShowYamlInput(false);
            setError(null);
            setSuccess(null);
        }
    }, [isOpen, computerLabel]);

    const fetchTemplates = async () => {
        setIsFetchingTemplates(true);
        try {
            const response = await frontendApi.get(`/infrastructure/computer/${computerLabel}/codes`);
            setTemplates(response.data);
        } catch (err) {
            console.error("Failed to fetch templates:", err);
        } finally {
            setIsFetchingTemplates(false);
        }
    };

    const handleTemplateChange = (pk: string) => {
        setSelectedTemplatePk(pk);
        if (pk === "none") return;

        const template = templates.find((t) => t.pk.toString() === pk);
        if (template) {
            setFormData({
                label: template.label,
                description: template.description || "",
                default_calc_job_plugin: template.default_calc_job_plugin,
                remote_abspath: template.remote_abspath,
                prepend_text: template.prepend_text || "",
                append_text: template.append_text || "",
                with_mpi: template.with_mpi,
                use_double_quotes: template.use_double_quotes,
            });
            setSuccess(`Applied template: ${template.label}`);
            setTimeout(() => setSuccess(null), 3000);
        }
    };

    const handleApplyYaml = () => {
        if (!yamlInput.trim()) return;

        try {
            const data: Record<string, any> = {};
            const lines = yamlInput.split(/\r?\n/);
            for (const line of lines) {
                // Use a more relaxed match for the value part
                const match = line.match(/^\s*([\w_-]+):\s*(.*)$/);
                if (match) {
                    const key = match[1].trim();
                    let value: string = match[2].trim();

                    // Clean up quotes (both ' and ")
                    if ((value.startsWith("'") && value.endsWith("'")) || (value.startsWith('"') && value.endsWith('"'))) {
                        value = value.substring(1, value.length - 1);
                    }

                    // Store as string first, then handle conversion during mapping
                    data[key] = value;
                }
            }

            // Map YAML keys to form data with correct type conversions
            const newFormData = { ...formData };
            let hasChanges = false;

            const applyValue = (key: string, targetField: keyof typeof formData, type: 'string' | 'boolean' | 'number' = 'string') => {
                if (Object.prototype.hasOwnProperty.call(data, key)) {
                    const rawValue = data[key];
                    if (type === 'string') {
                        (newFormData as any)[targetField] = String(rawValue);
                    } else if (type === 'boolean') {
                        (newFormData as any)[targetField] = String(rawValue).toLowerCase() === 'true';
                    } else if (type === 'number') {
                        (newFormData as any)[targetField] = Number(rawValue);
                    }
                    hasChanges = true;
                }
            };

            applyValue('label', 'label');
            applyValue('description', 'description');
            applyValue('default_calc_job_plugin', 'default_calc_job_plugin');
            applyValue('input_plugin', 'default_calc_job_plugin');
            applyValue('filepath_executable', 'remote_abspath');
            applyValue('remote_abspath', 'remote_abspath');
            applyValue('remote_abs_path', 'remote_abspath');
            applyValue('prepend_text', 'prepend_text');
            applyValue('append_text', 'append_text');
            applyValue('with_mpi', 'with_mpi', 'boolean');
            applyValue('use_double_quotes', 'use_double_quotes', 'boolean');

            if (hasChanges) {
                setFormData(newFormData);
                setSuccess("Configuration applied from YAML");
                setTimeout(() => setSuccess(null), 3000);
                setShowYamlInput(false);
            } else {
                setError("No valid configuration keys found in YAML");
            }
        } catch (err) {
            setError("Failed to parse YAML. Please check the format.");
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!formData.label || !formData.remote_abspath || !formData.default_calc_job_plugin) {
            setError("Please fill in all required fields (Label, Plugin, Executable Path)");
            return;
        }

        setIsLoading(true);
        setError(null);
        try {
            await frontendApi.post("/infrastructure/setup-code", {
                ...formData,
                computer_label: computerLabel,
            });
            onSuccess?.();
            onClose();
        } catch (err: any) {
            const errorMessage = err.response?.data?.detail?.error || err.response?.data?.error || err.message || "Failed to setup code";
            setError(errorMessage);
            console.error("Setup code error:", err);
        } finally {
            setIsLoading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-2xl w-full max-w-xl overflow-hidden flex flex-col max-h-[90vh]">
                <header className="px-6 py-4 border-b border-zinc-100 dark:border-zinc-900 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                            <Plus className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                        </div>
                        <div>
                            <h2 className="text-xl font-semibold tracking-tight">Setup Code</h2>
                            <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">On {computerLabel}</p>
                        </div>
                    </div>
                    <Button variant="ghost" size="icon" onClick={onClose}>
                        <X className="h-5 w-5" />
                    </Button>
                </header>

                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                    {/* Template and YAML Helpers */}
                    <div className="flex gap-4">
                        <div className="flex-1 p-4 bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-xl space-y-3">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2 text-zinc-500">
                                    <Copy className="h-4 w-4" />
                                    <span className="text-xs font-bold uppercase tracking-wider">Use as Template</span>
                                </div>
                            </div>
                            <CommandPaletteSelect
                                value={selectedTemplatePk}
                                options={[
                                    { value: "none", label: "Copy from existing code" },
                                    ...templates.map((template) => ({
                                        value: template.pk.toString(),
                                        label: template.label,
                                        description: template.default_calc_job_plugin,
                                        keywords: [template.default_calc_job_plugin, template.remote_abspath],
                                    })),
                                ]}
                                disabled={templates.length === 0}
                                ariaLabel="Select code template"
                                searchable={templates.length > 5}
                                className="w-full"
                                triggerClassName="flex w-full items-center justify-between rounded-lg px-2 py-2 text-sm"
                                onChange={handleTemplateChange}
                            />
                        </div>

                        <button
                            type="button"
                            onClick={() => setShowYamlInput(!showYamlInput)}
                            className={cn(
                                "flex-1 p-4 border rounded-xl space-y-3 text-left transition-all",
                                showYamlInput
                                    ? "bg-blue-50/50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800"
                                    : "bg-zinc-50 dark:bg-zinc-900/50 border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800/80"
                            )}
                        >
                            <div className="flex items-center gap-2 text-zinc-500">
                                <FileCode className={cn("h-4 w-4", showYamlInput && "text-blue-500")} />
                                <span className={cn("text-xs font-bold uppercase tracking-wider", showYamlInput && "text-blue-600 dark:text-blue-400")}>Paste Config</span>
                            </div>
                            <div className="h-4" /> {/* Spacer */}
                        </button>
                    </div>

                    {showYamlInput && (
                        <div className="space-y-3 animate-in slide-in-from-top-2 duration-300">
                                <textarea
                                    value={yamlInput}
                                    onChange={(e) => setYamlInput(e.target.value)}
                                    placeholder="label: my-code&#10;default_calc_job_plugin: plugin.calcjob&#10;filepath_executable: /path/to/executable&#10;..."
                                    className="w-full h-40 bg-zinc-900 text-zinc-100 border border-zinc-800 rounded-xl p-4 text-xs font-mono focus:ring-2 focus:ring-blue-500/50 outline-none transition-all resize-none shadow-inner"
                                />
                            <div className="flex justify-end gap-2">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setShowYamlInput(false)}
                                    className="h-8 text-xs"
                                >
                                    Cancel
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={handleApplyYaml}
                                    className="h-8 text-xs bg-zinc-800 hover:bg-zinc-700 text-white gap-1.5"
                                >
                                    <Wand2 className="h-3 w-3" />
                                    Apply Configuration
                                </Button>
                            </div>
                        </div>
                    )}

                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                            <label className="text-[10px] uppercase font-bold text-zinc-400 ml-1">Computer</label>
                            <input
                                value={computerLabel}
                                readOnly
                                className="w-full bg-zinc-100 dark:bg-zinc-900/70 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-zinc-500 dark:text-zinc-400"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-[10px] uppercase font-bold text-zinc-400 ml-1">Label *</label>
                            <input
                                placeholder="e.g. my-code"
                                value={formData.label}
                                onChange={(e) => setFormData({ ...formData, label: e.target.value })}
                                className="w-full bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all"
                                required
                            />
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-[10px] uppercase font-bold text-zinc-400 ml-1">Input Plugin *</label>
                            <input
                                placeholder="e.g. plugin.calcjob"
                                value={formData.default_calc_job_plugin}
                                onChange={(e) => setFormData({ ...formData, default_calc_job_plugin: e.target.value })}
                                className="w-full bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all font-mono"
                                required
                            />
                        </div>

                        <div className="col-span-2 space-y-1.5">
                            <label className="text-[10px] uppercase font-bold text-zinc-400 ml-1">Remote Absolute Path *</label>
                            <div className="relative">
                                <Terminal className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-400" />
                                <input
                                    placeholder="/path/to/executable"
                                    value={formData.remote_abspath}
                                    onChange={(e) => setFormData({ ...formData, remote_abspath: e.target.value })}
                                    className="w-full pl-10 bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all font-mono"
                                    required
                                />
                            </div>
                        </div>

                        <div className="col-span-2 space-y-1.5">
                            <label className="text-[10px] uppercase font-bold text-zinc-400 ml-1">Description</label>
                            <input
                                placeholder="Optional description"
                                value={formData.description}
                                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                className="w-full bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all"
                            />
                        </div>
                    </div>

                    <div className="rounded-xl border border-amber-200/70 bg-amber-50/70 px-4 py-3 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300">
                        This panel currently creates `InstalledCode` on the selected computer.
                        `--code-folder` and `--code-rel-path` for `store-in-db` codes are not supported here yet.
                    </div>

                    <div className="p-4 bg-zinc-50 dark:bg-zinc-900/30 rounded-xl border border-zinc-200 dark:border-zinc-800 space-y-4">
                        <div className="flex items-center gap-2 text-zinc-500">
                            <Settings2 className="h-4 w-4" />
                            <span className="text-xs font-bold uppercase tracking-wider">Execution Options</span>
                        </div>
                        <div className="flex gap-6">
                            <label className="flex items-center gap-2 cursor-pointer group">
                                <div
                                    onClick={() => setFormData({ ...formData, with_mpi: !formData.with_mpi })}
                                    className={cn(
                                        "w-5 h-5 rounded border flex items-center justify-center transition-all",
                                        formData.with_mpi ? "bg-blue-500 border-blue-500" : "bg-white dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700"
                                    )}
                                >
                                    {formData.with_mpi && <CheckCircle2 className="h-3.5 w-3.5 text-white" />}
                                </div>
                                <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Use MPI</span>
                            </label>

                            <label className="flex items-center gap-2 cursor-pointer group">
                                <div
                                    onClick={() => setFormData({ ...formData, use_double_quotes: !formData.use_double_quotes })}
                                    className={cn(
                                        "w-5 h-5 rounded border flex items-center justify-center transition-all",
                                        formData.use_double_quotes ? "bg-blue-500 border-blue-500" : "bg-white dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700"
                                    )}
                                >
                                    {formData.use_double_quotes && <CheckCircle2 className="h-3.5 w-3.5 text-white" />}
                                </div>
                                <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Double Quote Path</span>
                            </label>
                        </div>
                    </div>

                    <div className="space-y-4">
                        <div className="space-y-1.5">
                            <div className="flex items-center justify-between px-1">
                                <label className="text-[10px] uppercase font-bold text-zinc-400">Prepend Text</label>
                                <span className="text-[10px] text-zinc-400 italic">e.g. module load app/1.0</span>
                            </div>
                            <textarea
                                placeholder="Commands to run before the executable..."
                                value={formData.prepend_text}
                                onChange={(e) => setFormData({ ...formData, prepend_text: e.target.value })}
                                className="w-full h-24 bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 text-xs font-mono focus:ring-2 focus:ring-blue-500/20 outline-none transition-all resize-none"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <div className="flex items-center justify-between px-1">
                                <label className="text-[10px] uppercase font-bold text-zinc-400">Append Text</label>
                                <span className="text-[10px] text-zinc-400 italic">Optional cleanup</span>
                            </div>
                            <textarea
                                placeholder="Commands to run after the executable..."
                                value={formData.append_text}
                                onChange={(e) => setFormData({ ...formData, append_text: e.target.value })}
                                className="w-full h-16 bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 text-xs font-mono focus:ring-2 focus:ring-blue-500/20 outline-none transition-all resize-none"
                            />
                        </div>
                    </div>

                    {error && (
                        <div className="p-3 bg-rose-50 dark:bg-rose-900/20 border border-rose-100 dark:border-rose-900/30 rounded-xl flex gap-x-2 text-rose-600 dark:text-rose-400 text-sm animate-in shake duration-300">
                            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                            {error}
                        </div>
                    )}

                    {success && (
                        <div className="p-3 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-900/30 rounded-xl flex gap-x-2 text-emerald-600 dark:text-emerald-400 text-sm animate-in fade-in duration-300">
                            <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                            {success}
                        </div>
                    )}
                </div>

                <footer className="px-6 py-4 border-t border-zinc-100 dark:border-zinc-900 bg-zinc-50/50 dark:bg-zinc-900/50 flex items-center justify-end gap-3">
                    <Button variant="ghost" onClick={onClose} disabled={isLoading}>Cancel</Button>
                    <Button
                        disabled={isLoading}
                        onClick={handleSubmit}
                        className="bg-blue-600 hover:bg-blue-700 text-white rounded-xl px-8 font-semibold gap-2 shadow-lg shadow-blue-500/20"
                    >
                        {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                        Save Code
                    </Button>
                </footer>
            </div>
        </div>
    );
}

function Settings2(props: any) {
    return (
        <svg
            {...props}
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <path d="M20 7h-9" />
            <path d="M14 17H5" />
            <circle cx="17" cy="17" r="3" />
            <circle cx="7" cy="7" r="3" />
        </svg>
    );
}


import React, { useCallback, useEffect, useState } from "react";
import {
    X,
    Upload,
    Terminal,
    Cpu,
    Code2,
    Loader2,
    CheckCircle2,
    AlertCircle,
    Wand2,
    Settings2,
    Sparkles,
    ChevronDown,
    ChevronUp
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { CommandPaletteSelect } from "@/components/ui/command-palette-select";
import type { ParseInfrastructureResponse } from "@/types/aiida";
import { cn } from "@/lib/utils";
import {
    getInfrastructureCapabilities,
    getSshHosts,
    parseInfrastructure,
    setupInfrastructure,
    type SSHHostDetails,
} from "@/lib/api";
import { useQuery } from "@tanstack/react-query";

type QuickAddModalProps = {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
};

type InfrastructureParseData = ParseInfrastructureResponse["data"];
const SYNC_SSH_TRANSPORT = "core.ssh";
const ASYNC_SSH_TRANSPORT = "core.ssh_async";
const LOCAL_TRANSPORT = "core.local";

function buildDefaultComputerConfig(
    recommendedTransport = SYNC_SSH_TRANSPORT,
): NonNullable<InfrastructureParseData["computer"]> {
    const isAsyncTransport = recommendedTransport === ASYNC_SSH_TRANSPORT;
    return {
        label: "",
        hostname: "",
        username: "",
        description: "",
        transport_type: recommendedTransport,
        scheduler_type: "core.direct",
        shebang: "#!/bin/bash",
        work_dir: "/tmp/aiida",
        mpiprocs_per_machine: 1,
        mpirun_command: "mpirun -np {tot_num_mpiprocs}",
        default_memory_per_machine: null,
        use_double_quotes: false,
        prepend_text: "",
        append_text: "",
        key_filename: "",
        proxy_command: "",
        proxy_jump: "",
        safe_interval: 0,
        use_login_shell: true,
        connection_timeout: isAsyncTransport ? null : 60,
        host: "",
        max_io_allowed: null,
        authentication_script: "",
        backend: isAsyncTransport ? "asyncssh" : "",
    };
}

const DEFAULT_CODE_CONFIG: NonNullable<InfrastructureParseData["code"]> = {
    label: "",
    description: "",
    default_calc_job_plugin: "",
    remote_abspath: "",
    prepend_text: "",
    append_text: "",
};

function createEmptyParseResult(recommendedTransport = SYNC_SSH_TRANSPORT): InfrastructureParseData {
    return {
        type: "computer",
        preset_matched: false,
        preset_domain: "",
        computer: { ...buildDefaultComputerConfig(recommendedTransport) },
        code: { ...DEFAULT_CODE_CONFIG },
    };
}

function mergeParseResult(
    raw?: InfrastructureParseData | null,
    recommendedTransport = SYNC_SSH_TRANSPORT,
): InfrastructureParseData {
    const defaultComputerConfig = buildDefaultComputerConfig(recommendedTransport);
    return {
        type: raw?.type ?? "computer",
        preset_matched: Boolean(raw?.preset_matched),
        preset_domain: raw?.preset_domain ?? "",
        computer: {
            ...defaultComputerConfig,
            ...(raw?.computer ?? {}),
        },
        code: {
            ...DEFAULT_CODE_CONFIG,
            ...(raw?.code ?? {}),
        },
    };
}

export function QuickAddModal({ isOpen, onClose, onSuccess }: QuickAddModalProps) {
    const [pasteText, setPasteText] = useState("");
    const [isParsing, setIsParsing] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [parseResult, setParseResult] = useState<InfrastructureParseData>(() => createEmptyParseResult());
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<"paste" | "form">("paste");

    const [showAdvanced, setShowAdvanced] = useState(false);
    const [selectedSshHost, setSelectedSshHost] = useState<string>("");

    const capabilitiesQuery = useQuery({
        queryKey: ["infrastructure-capabilities"],
        queryFn: getInfrastructureCapabilities,
    });
    const capabilities = capabilitiesQuery.data;
    const recommendedTransport = capabilities?.recommended_transport || SYNC_SSH_TRANSPORT;
    const availableTransports = capabilities?.available_transports?.length
        ? capabilities.available_transports
        : [LOCAL_TRANSPORT, SYNC_SSH_TRANSPORT];

    const sshHostsQuery = useQuery({
        queryKey: ["ssh-hosts"],
        queryFn: getSshHosts,
    });
    const sshHosts = sshHostsQuery.data || [];

    useEffect(() => {
        if (!isOpen) {
            return;
        }
        setPasteText("");
        setIsParsing(false);
        setIsSubmitting(false);
        setError(null);
        setActiveTab("paste");
        setShowAdvanced(false);
        setSelectedSshHost("");
        setParseResult(createEmptyParseResult(recommendedTransport));
    }, [isOpen, recommendedTransport]);

    useEffect(() => {
        if (!isOpen || !capabilities) {
            return;
        }
        setParseResult((current) => {
            const computer = current.computer ?? {};
            const isPristine = !computer.label && !computer.hostname && !computer.username;
            if (!isPristine || (computer.transport_type && computer.transport_type !== SYNC_SSH_TRANSPORT)) {
                return current;
            }
            return mergeParseResult(current, recommendedTransport);
        });
    }, [capabilities, isOpen, recommendedTransport]);

    const updateComputer = useCallback((patch: Partial<NonNullable<InfrastructureParseData["computer"]>>) => {
        setParseResult((current) => ({
            ...current,
            computer: {
                ...buildDefaultComputerConfig(recommendedTransport),
                ...(current.computer ?? {}),
                ...patch,
            },
        }));
    }, [recommendedTransport]);

    const updateCode = useCallback((patch: Partial<NonNullable<InfrastructureParseData["code"]>>) => {
        setParseResult((current) => ({
            ...current,
            code: {
                ...DEFAULT_CODE_CONFIG,
                ...(current.code ?? {}),
                ...patch,
            },
        }));
    }, []);

    const handleTransportChange = useCallback((nextTransport: string) => {
        setParseResult((current) => {
            const base = {
                ...buildDefaultComputerConfig(recommendedTransport),
                ...(current.computer ?? {}),
                transport_type: nextTransport,
            };

            if (nextTransport === ASYNC_SSH_TRANSPORT) {
                return {
                    ...current,
                    computer: {
                        ...base,
                        username: "",
                        key_filename: "",
                        proxy_command: "",
                        proxy_jump: "",
                        connection_timeout: null,
                        host: base.host || base.hostname || selectedSshHost || "",
                        backend: base.backend || "asyncssh",
                    },
                };
            }

            if (nextTransport === LOCAL_TRANSPORT) {
                return {
                    ...current,
                    computer: {
                        ...base,
                        username: "",
                        key_filename: "",
                        proxy_command: "",
                        proxy_jump: "",
                        host: "",
                        max_io_allowed: null,
                        authentication_script: "",
                        backend: "",
                        connection_timeout: null,
                    },
                };
            }

            return {
                ...current,
                computer: {
                    ...base,
                    host: "",
                    max_io_allowed: null,
                    authentication_script: "",
                    backend: "",
                    connection_timeout: base.connection_timeout ?? 60,
                },
            };
        });
    }, [recommendedTransport, selectedSshHost]);

    const handleParse = async () => {
        if (!pasteText.trim() && !selectedSshHost) return;
        setIsParsing(true);
        setError(null);
        try {
            const hostDetails = sshHosts.find(h => h.alias === selectedSshHost) || null;
            const textToParse = pasteText.trim() || `Configure computer for SSH host ${selectedSshHost}`;

            const response = await parseInfrastructure(textToParse, hostDetails);
            if (response.status === "success" && response.data) {
                setParseResult(mergeParseResult(response.data, recommendedTransport));
                setActiveTab("form");
            } else {
                setError("Failed to parse input. Please try again or fill manually.");
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || "AI Parsing failed.");
        } finally {
            setIsParsing(false);
        }
    };

    const handleSubmit = async () => {
        if (!parseResult || !parseResult.computer) {
            setError("Computer configuration is missing.");
            return;
        }
        const transportType = parseResult.computer.transport_type || recommendedTransport;
        if (!availableTransports.includes(transportType)) {
            setError(
                `Transport ${transportType} is not available for aiida-core ${capabilities?.aiida_core_version || "this installation"}.`,
            );
            return;
        }
        if (transportType === ASYNC_SSH_TRANSPORT) {
            const legacyFields = ["username", "key_filename", "proxy_command", "proxy_jump", "connection_timeout"]
                .filter((field) => {
                    const value = (parseResult.computer as Record<string, unknown>)[field];
                    return value !== null && value !== undefined && value !== "";
                });
            if (legacyFields.length > 0) {
                setError(
                    `core.ssh_async does not accept legacy SSH fields: ${legacyFields.join(", ")}. Use SSH host alias, backend, authentication script, and max I/O instead.`,
                );
                return;
            }
        }
        setIsSubmitting(true);
        setError(null);

        try {
            const payload: Record<string, any> = {
                computer_label: parseResult.computer.label || "unknown_computer",
                hostname: parseResult.computer.hostname || "unknown_host",
                username: parseResult.computer.username || "",
                computer_description: parseResult.computer.description || "",
                transport_type: transportType,
                scheduler_type: parseResult.computer.scheduler_type || "core.direct",
                shebang: parseResult.computer.shebang || "#!/bin/bash",
                work_dir: parseResult.computer.work_dir || "/tmp/aiida",
                mpiprocs_per_machine: parseResult.computer.mpiprocs_per_machine || 1,
                mpirun_command: parseResult.computer.mpirun_command || "mpirun -np {tot_num_mpiprocs}",
                default_memory_per_machine: parseResult.computer.default_memory_per_machine ?? null,
                use_double_quotes: parseResult.computer.use_double_quotes === true,
                prepend_text: parseResult.computer.prepend_text || "",
                append_text: parseResult.computer.append_text || "",
                use_login_shell: parseResult.computer.use_login_shell !== false,
                safe_interval: parseResult.computer.safe_interval || 0.0,
                connection_timeout: parseResult.computer.connection_timeout ?? null,
                key_filename: parseResult.computer.key_filename || "",
                proxy_command: parseResult.computer.proxy_command || "",
                proxy_jump: parseResult.computer.proxy_jump || "",
                host: parseResult.computer.host || "",
                max_io_allowed: parseResult.computer.max_io_allowed ?? null,
                authentication_script: parseResult.computer.authentication_script || "",
                backend: parseResult.computer.backend || "",
            };

            const code = parseResult.code;
            if (code && code.label && code.default_calc_job_plugin && code.remote_abspath) {
                payload.code_label = code.label;
                payload.code_description = code.description || "";
                payload.default_calc_job_plugin = code.default_calc_job_plugin;
                payload.remote_abspath = code.remote_abspath;
                payload.code_prepend_text = code.prepend_text || "";
                payload.code_append_text = code.append_text || "";
            }

            const response = await setupInfrastructure(payload);
            if (response.connection_status === "failed") {
                setError(`Setup partial via DB, but connection test failed: ${response.connection_error}`);
            } else {
                onSuccess();
                onClose();
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || "Submission failed.");
        } finally {
            setIsSubmitting(false);
        }
    };


    const selectedTransport = parseResult.computer?.transport_type || recommendedTransport;
    const isAsyncTransport = selectedTransport === ASYNC_SSH_TRANSPORT;
    const isLocalTransport = selectedTransport === LOCAL_TRANSPORT;

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-2xl w-full max-w-4xl overflow-hidden flex flex-col max-h-[90vh]">
                <header className="px-6 py-4 border-b border-zinc-100 dark:border-zinc-900 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="p-2 bg-zinc-100 dark:bg-zinc-900 rounded-lg">
                            <Plus className="h-5 w-5 text-zinc-600 dark:text-zinc-400" />
                        </div>
                        <h2 className="text-xl font-semibold tracking-tight">Quick Add Infrastructure</h2>
                    </div>
                    <Button variant="ghost" size="icon" onClick={onClose}>
                        <X className="h-5 w-5" />
                    </Button>
                </header>

                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                    <div className="flex gap-2 p-1 bg-zinc-100 dark:bg-zinc-900 rounded-xl">
                        <button
                            onClick={() => setActiveTab("paste")}
                            className={cn(
                                "flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-lg transition-all",
                                activeTab === "paste" ? "bg-white dark:bg-zinc-800 shadow-sm" : "text-zinc-500"
                            )}
                        >
                            <Terminal className="h-4 w-4" />
                            Drop & Paste
                        </button>
                        <button
                            onClick={() => setActiveTab("form")}
                            className={cn(
                                "flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-lg transition-all",
                                activeTab === "form" ? "bg-white dark:bg-zinc-800 shadow-sm" : "text-zinc-500"
                            )}
                        >
                            <Settings2 className="h-4 w-4" />
                            Review Setup
                        </button>
                    </div>

                    {activeTab === "paste" ? (
                        <div className="space-y-4">
                            <div className="relative group">
                                <textarea
                                    value={pasteText}
                                    onChange={(e) => setPasteText(e.target.value)}
                                    placeholder="Paste an SSH command, YAML snippet, or describe your computer..."
                                    className="w-full h-48 bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 text-sm font-mono focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all resize-none"
                                />
                                <div className="absolute top-4 right-4 text-zinc-400 group-hover:text-blue-500 transition-colors">
                                    <Upload className="h-5 w-5" />
                                </div>
                            </div>

                            <div className="flex flex-col gap-2">
                                <label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                                    Or Select Existing SSH Host
                                </label>
                                <CommandPaletteSelect
                                    value={selectedSshHost}
                                    options={[
                                        { value: "", label: "No SSH Host Selected" },
                                        ...sshHosts.map((host) => ({
                                            value: host.alias,
                                            label: host.alias,
                                            description: host.hostname || null,
                                            keywords: [host.hostname || ""],
                                        })),
                                    ]}
                                    ariaLabel="Select existing SSH host"
                                    searchable={sshHosts.length > 6}
                                    className="w-full"
                                    triggerClassName="flex w-full items-center justify-between rounded-lg px-2 py-2 text-sm"
                                    onChange={setSelectedSshHost}
                                />
                            </div>

                            <div className="bg-blue-50/50 dark:bg-blue-900/20 border border-blue-100/50 dark:border-blue-900/30 rounded-xl p-4 flex gap-3">
                                <Wand2 className="h-5 w-5 text-blue-500 shrink-0" />
                                <div className="space-y-1 text-sm text-blue-700 dark:text-blue-300">
                                    <p>
                                        Tip: paste exported computer YAML, scheduler snippets, or select an SSH host alias. Structured YAML is parsed locally before AI fallback.
                                    </p>
                                    <p className="text-xs">
                                        aiida-core: <span className="font-mono">{capabilities?.aiida_core_version || "detecting..."}</span>
                                        {" · "}
                                        transports: <span className="font-mono">{availableTransports.join(", ")}</span>
                                    </p>
                                </div>
                            </div>

                            <Button
                                onClick={handleParse}
                                className="w-full h-12 bg-zinc-900 dark:bg-zinc-100 hover:bg-zinc-800 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 rounded-xl font-semibold gap-2"
                                disabled={isParsing || (!pasteText.trim() && !selectedSshHost)}
                            >
                                {isParsing ? <Loader2 className="h-5 w-5 animate-spin" /> : <Wand2 className="h-5 w-5" />}
                                Analyze and Auto-fill
                            </Button>
                        </div>
                    ) : (
                        <div className="space-y-6 animate-in slide-in-from-right-2 duration-300">
                                <div className="space-y-6">
                                    {parseResult.preset_matched && (
                                        <div className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-xl p-4 flex gap-3 animate-in fade-in zoom-in-95">
                                            <Sparkles className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                                            <div>
                                                <h4 className="text-sm font-semibold text-emerald-800 dark:text-emerald-300">Preset Applied Automatically</h4>
                                                <p className="text-sm text-emerald-700 dark:text-emerald-400 mt-1">
                                                    Identified domain <code className="font-mono text-xs bg-emerald-100 dark:bg-emerald-900/50 px-1 py-0.5 rounded">{parseResult.preset_domain}</code>. Known parameters have been pre-filled. You can review them in Advanced Settings.
                                                </p>
                                            </div>
                                        </div>
                                    )}
                                    {parseResult.computer && (
                                        <div className="p-4 bg-zinc-50 dark:bg-zinc-900/30 rounded-xl border border-zinc-200 dark:border-zinc-800 space-y-4">
                                            <div className="flex items-center gap-2 text-zinc-500">
                                                <Cpu className="h-4 w-4" />
                                                <span className="text-xs font-bold uppercase tracking-wider">Basic Configuration</span>
                                            </div>
                                            <div className="grid grid-cols-2 gap-4">
                                                <div className="space-y-1">
                                                    <label className="text-[10px] uppercase font-bold text-zinc-400">Label</label>
                                                    <input
                                                        value={parseResult.computer.label || ""}
                                                        onChange={(e) => updateComputer({ label: e.target.value })}
                                                        className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                                                    />
                                                </div>
                                                <div className="space-y-1">
                                                    <label className="text-[10px] uppercase font-bold text-zinc-400">Hostname</label>
                                                    <input
                                                        value={parseResult.computer.hostname || ""}
                                                        onChange={(e) => updateComputer({ hostname: e.target.value })}
                                                        className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                                                    />
                                                </div>
                                                <div className="space-y-1 col-span-2">
                                                    <label className="text-[10px] uppercase font-bold text-zinc-400">Description</label>
                                                    <input
                                                        value={parseResult.computer.description || ""}
                                                        onChange={(e) => updateComputer({ description: e.target.value })}
                                                        className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                                                    />
                                                </div>
                                                <div className="space-y-1">
                                                    <label className="text-[10px] uppercase font-bold text-zinc-400">Transport Type</label>
                                                    <select
                                                        value={selectedTransport}
                                                        onChange={(e) => handleTransportChange(e.target.value)}
                                                        className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                                                    >
                                                        {availableTransports.map((transport) => (
                                                            <option key={transport} value={transport}>{transport}</option>
                                                        ))}
                                                    </select>
                                                </div>
                                                <div className="space-y-1">
                                                    <label className="text-[10px] uppercase font-bold text-zinc-400">Scheduler Type</label>
                                                    <input
                                                        value={parseResult.computer.scheduler_type || ""}
                                                        onChange={(e) => updateComputer({ scheduler_type: e.target.value })}
                                                        className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                                                    />
                                                </div>
                                                {isAsyncTransport ? (
                                                    <div className="space-y-1">
                                                        <label className="text-[10px] uppercase font-bold text-zinc-400">SSH Host Alias</label>
                                                        <input
                                                            value={parseResult.computer.host || ""}
                                                            onChange={(e) => updateComputer({ host: e.target.value })}
                                                            placeholder="Host entry from ~/.ssh/config"
                                                            className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                                                        />
                                                    </div>
                                                ) : !isLocalTransport ? (
                                                    <div className="space-y-1">
                                                        <label className="text-[10px] uppercase font-bold text-zinc-400">Username</label>
                                                        <input
                                                            value={parseResult.computer.username || ""}
                                                            onChange={(e) => updateComputer({ username: e.target.value })}
                                                            className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                                                        />
                                                    </div>
                                                ) : (
                                                    <div className="rounded-lg border border-dashed border-zinc-200 dark:border-zinc-800 px-3 py-2 text-xs text-zinc-500 dark:text-zinc-400">
                                                        Local transport does not require remote SSH authentication fields.
                                                    </div>
                                                )}
                                                <div className="space-y-1 col-span-2">
                                                    <label className="text-[10px] uppercase font-bold text-zinc-400">Work Directory</label>
                                                    <input
                                                        value={parseResult.computer.work_dir || ""}
                                                        onChange={(e) => updateComputer({ work_dir: e.target.value })}
                                                        className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                                                    />
                                                </div>
                                                <div className="space-y-1">
                                                    <label className="text-[10px] uppercase font-bold text-zinc-400">MPI Procs / Machine</label>
                                                    <input
                                                        type="number"
                                                        value={parseResult.computer.mpiprocs_per_machine || ""}
                                                        onChange={(e) => updateComputer({ mpiprocs_per_machine: parseInt(e.target.value, 10) || 1 })}
                                                        className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                                                    />
                                                </div>
                                                <div className="space-y-1">
                                                    <label className="text-[10px] uppercase font-bold text-zinc-400">Default Memory / Machine (kB)</label>
                                                    <input
                                                        type="number"
                                                        value={parseResult.computer.default_memory_per_machine ?? ""}
                                                        onChange={(e) => updateComputer({ default_memory_per_machine: e.target.value ? parseInt(e.target.value, 10) || null : null })}
                                                        className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                                                    />
                                                </div>
                                                <div className="space-y-1 col-span-2">
                                                    <label className="text-[10px] uppercase font-bold text-zinc-400">MPI Run Command</label>
                                                    <input
                                                        value={parseResult.computer.mpirun_command || ""}
                                                        onChange={(e) => updateComputer({ mpirun_command: e.target.value })}
                                                        className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                                                    />
                                                </div>
                                            </div>

                                            {isAsyncTransport && (
                                                <div className="rounded-lg border border-amber-200/70 bg-amber-50/80 px-3 py-2 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300">
                                                    <span className="font-semibold">core.ssh_async</span> follows the async SSH configure model from AiiDA 2.7+: it uses an SSH config alias and does not use legacy fields like <code className="font-mono">username</code>, <code className="font-mono">key_filename</code>, or <code className="font-mono">proxy_jump</code>.
                                                </div>
                                            )}

                                            <button
                                                onClick={() => setShowAdvanced(!showAdvanced)}
                                                className="flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700 dark:text-blue-400 pt-2 transition-colors"
                                            >
                                                {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                                                {showAdvanced ? "Hide Advanced Settings" : "Show Advanced Settings"}
                                            </button>

                                            {showAdvanced && (
                                                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-zinc-200 dark:border-zinc-800 animate-in slide-in-from-top-2 duration-200">
                                                    <div className="space-y-1">
                                                        <label className="text-[10px] uppercase font-bold text-zinc-400">Shebang</label>
                                                        <input value={parseResult.computer.shebang || ""} onChange={(e) => updateComputer({ shebang: e.target.value })} className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-100 outline-none transition-all text-zinc-600 dark:text-zinc-400" />
                                                    </div>
                                                    <div className="space-y-1">
                                                        <label className="text-[10px] uppercase font-bold text-zinc-400">Safe Interval</label>
                                                        <input type="number" step="0.1" value={parseResult.computer.safe_interval ?? ""} onChange={(e) => updateComputer({ safe_interval: parseFloat(e.target.value) || 0 })} className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-100 outline-none transition-all text-zinc-600 dark:text-zinc-400" />
                                                    </div>
                                                    {isAsyncTransport ? (
                                                        <>
                                                            <div className="space-y-1">
                                                                <label className="text-[10px] uppercase font-bold text-zinc-400">Max I/O Allowed</label>
                                                                <input type="number" value={parseResult.computer.max_io_allowed ?? ""} onChange={(e) => updateComputer({ max_io_allowed: e.target.value ? parseInt(e.target.value, 10) || null : null })} className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-100 outline-none transition-all text-zinc-600 dark:text-zinc-400" />
                                                            </div>
                                                            <div className="space-y-1">
                                                                <label className="text-[10px] uppercase font-bold text-zinc-400">Authentication Script</label>
                                                                <input value={parseResult.computer.authentication_script || ""} onChange={(e) => updateComputer({ authentication_script: e.target.value })} className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-100 outline-none transition-all text-zinc-600 dark:text-zinc-400" />
                                                            </div>
                                                            <div className="space-y-1">
                                                                <label className="text-[10px] uppercase font-bold text-zinc-400">Async Backend</label>
                                                                <select value={parseResult.computer.backend || "asyncssh"} onChange={(e) => updateComputer({ backend: e.target.value })} className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-100 outline-none transition-all text-zinc-600 dark:text-zinc-400">
                                                                    <option value="asyncssh">asyncssh</option>
                                                                    <option value="openssh">openssh</option>
                                                                </select>
                                                            </div>
                                                        </>
                                                    ) : !isLocalTransport ? (
                                                        <>
                                                            <div className="space-y-1">
                                                                <label className="text-[10px] uppercase font-bold text-zinc-400">Key File</label>
                                                                <input value={parseResult.computer.key_filename || ""} onChange={(e) => updateComputer({ key_filename: e.target.value })} className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-100 outline-none transition-all text-zinc-600 dark:text-zinc-400" />
                                                            </div>
                                                            <div className="space-y-1">
                                                                <label className="text-[10px] uppercase font-bold text-zinc-400">Proxy Command</label>
                                                                <input value={parseResult.computer.proxy_command || ""} onChange={(e) => updateComputer({ proxy_command: e.target.value })} className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-100 outline-none transition-all text-zinc-600 dark:text-zinc-400" />
                                                            </div>
                                                            <div className="space-y-1">
                                                                <label className="text-[10px] uppercase font-bold text-zinc-400">Proxy Jump</label>
                                                                <input value={parseResult.computer.proxy_jump || ""} onChange={(e) => updateComputer({ proxy_jump: e.target.value })} className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-100 outline-none transition-all text-zinc-600 dark:text-zinc-400" />
                                                            </div>
                                                            <div className="space-y-1">
                                                                <label className="text-[10px] uppercase font-bold text-zinc-400">Connection Timeout</label>
                                                                <input type="number" value={parseResult.computer.connection_timeout ?? ""} onChange={(e) => updateComputer({ connection_timeout: e.target.value ? parseInt(e.target.value, 10) || 60 : null })} className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-100 outline-none transition-all text-zinc-600 dark:text-zinc-400" />
                                                            </div>
                                                        </>
                                                    ) : (
                                                        <div className="col-span-1 rounded-lg border border-dashed border-zinc-200 dark:border-zinc-800 px-3 py-2 text-xs text-zinc-500 dark:text-zinc-400">
                                                            No additional transport-specific authentication fields are required for <code className="font-mono">core.local</code>.
                                                        </div>
                                                    )}
                                                    <button
                                                        type="button"
                                                        onClick={() => updateComputer({ use_double_quotes: !parseResult.computer?.use_double_quotes })}
                                                        className={cn(
                                                            "flex items-center justify-between rounded-lg border px-3 py-2 text-sm transition-colors",
                                                            parseResult.computer.use_double_quotes
                                                                ? "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-300"
                                                                : "border-zinc-200 bg-white text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300",
                                                        )}
                                                    >
                                                        <span className="text-[11px] font-semibold uppercase tracking-wider">Use Double Quotes</span>
                                                        <span>{parseResult.computer.use_double_quotes ? "Enabled" : "Disabled"}</span>
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => updateComputer({ use_login_shell: parseResult.computer?.use_login_shell === false })}
                                                        className={cn(
                                                            "flex items-center justify-between rounded-lg border px-3 py-2 text-sm transition-colors",
                                                            parseResult.computer.use_login_shell !== false
                                                                ? "border-zinc-200 bg-white text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200"
                                                                : "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300",
                                                        )}
                                                    >
                                                        <span className="text-[11px] font-semibold uppercase tracking-wider">Use Login Shell</span>
                                                        <span>{parseResult.computer.use_login_shell !== false ? "Enabled" : "Disabled"}</span>
                                                    </button>
                                                    <div className="space-y-1 col-span-2">
                                                        <label className="text-[10px] uppercase font-bold text-zinc-400">Prepend Text</label>
                                                        <textarea value={parseResult.computer.prepend_text || ""} onChange={(e) => updateComputer({ prepend_text: e.target.value })} className="w-full h-24 bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-100 outline-none transition-all font-mono whitespace-pre text-zinc-600 dark:text-zinc-400" />
                                                    </div>
                                                    <div className="space-y-1 col-span-2">
                                                        <label className="text-[10px] uppercase font-bold text-zinc-400">Append Text</label>
                                                        <textarea value={parseResult.computer.append_text || ""} onChange={(e) => updateComputer({ append_text: e.target.value })} className="w-full h-24 bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-100 outline-none transition-all font-mono whitespace-pre text-zinc-600 dark:text-zinc-400" />
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {parseResult.code && Object.keys(parseResult.code).length > 0 && (
                                        <div className="p-4 bg-zinc-50 dark:bg-zinc-900/30 rounded-xl border border-zinc-200 dark:border-zinc-800 space-y-4">
                                            <div className="flex items-center gap-2 text-zinc-500">
                                                <Code2 className="h-4 w-4" />
                                                <span className="text-xs font-bold uppercase tracking-wider">Default Code Configuration</span>
                                            </div>
                                            <div className="grid grid-cols-2 gap-4">
                                                <div className="space-y-1">
                                                    <label className="text-[10px] uppercase font-bold text-zinc-400">Target Plugin</label>
                                                    <input
                                                        value={parseResult.code.default_calc_job_plugin || ""}
                                                        onChange={(e) => updateCode({ default_calc_job_plugin: e.target.value })}
                                                        className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-100 outline-none"
                                                    />
                                                </div>
                                                <div className="space-y-1">
                                                    <label className="text-[10px] uppercase font-bold text-zinc-400">Code Label</label>
                                                    <input
                                                        value={parseResult.code.label || ""}
                                                        onChange={(e) => updateCode({ label: e.target.value })}
                                                        className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-100 outline-none"
                                                        placeholder="e.g., pw"
                                                    />
                                                </div>
                                                <div className="col-span-2 space-y-1">
                                                    <label className="text-[10px] uppercase font-bold text-zinc-400">Remote Executable Path</label>
                                                    <input
                                                        value={parseResult.code.remote_abspath || ""}
                                                        onChange={(e) => updateCode({ remote_abspath: e.target.value })}
                                                        className="w-full bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-100 outline-none"
                                                    />
                                                </div>
                                                <div className="col-span-2 space-y-1">
                                                    <label className="text-[10px] uppercase font-bold text-zinc-400">Code Prepend Text</label>
                                                    <textarea
                                                        value={parseResult.code.prepend_text || ""}
                                                        onChange={(e) => updateCode({ prepend_text: e.target.value })}
                                                        className="w-full h-20 bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-100 outline-none"
                                                    />
                                                </div>
                                                <div className="col-span-2 space-y-1">
                                                    <label className="text-[10px] uppercase font-bold text-zinc-400">Code Append Text</label>
                                                    <textarea
                                                        value={parseResult.code.append_text || ""}
                                                        onChange={(e) => updateCode({ append_text: e.target.value })}
                                                        className="w-full h-20 bg-white dark:bg-zinc-800 border-none rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-100 outline-none"
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                        </div>
                    )}

                    {error && (
                        <div className="p-3 bg-rose-50 dark:bg-rose-900/20 border border-rose-100 dark:border-rose-900/30 rounded-xl flex gap-x-2 text-rose-600 dark:text-rose-400 text-sm">
                            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                            {error}
                        </div>
                    )}
                </div>

                <footer className="px-6 py-4 border-t border-zinc-100 dark:border-zinc-900 bg-zinc-50/50 dark:bg-zinc-900/50 flex items-center justify-end gap-3">
                    <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>Cancel</Button>
                    <Button
                        disabled={!parseResult || isSubmitting}
                        onClick={handleSubmit}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl px-6 gap-2"
                    >
                        {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                        Test Connection & Save
                    </Button>
                </footer>
            </div>
        </div>
    );
}

function Plus(props: any) {
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
            <path d="M5 12h14" />
            <path d="M12 5v14" />
        </svg>
    );
}

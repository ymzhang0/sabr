import React, { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
    X,
    User,
    Mail,
    Database,
    FolderOpen,
    Loader2,
    CheckCircle2,
    AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getCurrentUserInfo, setupProfile, switchBridgeProfile } from "@/lib/api";
import type { ProfileSetupRequest } from "@/types/aiida";

type NewProfileDrawerProps = {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
};

export function NewProfileDrawer({ isOpen, onClose, onSuccess }: NewProfileDrawerProps) {
    const queryClient = useQueryClient();
    const nameInputRef = useRef<HTMLInputElement>(null);

    const [form, setForm] = useState<ProfileSetupRequest>({
        profile_name: "",
        first_name: "",
        last_name: "",
        email: "",
        institution: "",
        filepath: "",
        backend: "core.sqlite_dos",
        set_as_default: true,
    });

    const [rabbitmq, setRabbitmq] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const userInfoQuery = useQuery({
        queryKey: ["current-user-info"],
        queryFn: getCurrentUserInfo,
        enabled: isOpen,
        staleTime: 0,
    });

    useEffect(() => {
        if (isOpen) {
            setForm((prev: ProfileSetupRequest) => ({
                ...prev,
                profile_name: "",
                filepath: "",
            }));
            setError(null);
            // Longer timeout for drawer transition
            setTimeout(() => nameInputRef.current?.focus(), 350);
        }
    }, [isOpen]);

    useEffect(() => {
        if (userInfoQuery.data) {
            setForm((prev: ProfileSetupRequest) => ({
                ...prev,
                first_name: userInfoQuery.data.first_name || prev.first_name,
                last_name: userInfoQuery.data.last_name || prev.last_name,
                email: userInfoQuery.data.email || prev.email,
                institution: userInfoQuery.data.institution || prev.institution,
            }));
        }
    }, [userInfoQuery.data]);

    const setupMutation = useMutation({
        mutationFn: setupProfile,
        onSuccess: async (data) => {
            if (form.set_as_default) {
                await switchBridgeProfile(data.profile_name);
            }
            queryClient.invalidateQueries({ queryKey: ["aiida-bridge-profiles"] });
            queryClient.invalidateQueries({ queryKey: ["aiida-bridge-status"] });
            onSuccess();
            onClose();
        },
        onError: (err: any) => {
            setError(err.response?.data?.detail || err.message || "Failed to setup new profile.");
        },
    });

    const isSubmitting = setupMutation.isPending;

    const drawerContent = (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 z-[90] bg-black/40 backdrop-blur-sm animate-in fade-in duration-300"
                onClick={onClose}
            />

            {/* Drawer */}
            <aside
                className="absolute top-0 left-[calc(100%+16px)] z-[100] flex flex-col w-[420px] 
                bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 
                rounded-2xl shadow-2xl overflow-hidden
                /* Dynamic height logic: adaptive height, but capped at screen height minus margins */
                h-auto max-h-[calc(100vh-100px)] 
                animate-in slide-in-from-left duration-300"
            >
                <header className="flex-none px-6 py-4 border-b border-zinc-100 dark:border-zinc-900 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="p-2 bg-zinc-100 dark:bg-zinc-900 rounded-lg">
                            <Database className="h-5 w-5 text-zinc-600 dark:text-zinc-400" />
                        </div>
                        <h2 className="text-lg font-semibold tracking-tight dark:text-zinc-100">Create New Profile</h2>
                    </div>
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose} disabled={isSubmitting}>
                        <X className="h-4 w-4" />
                    </Button>
                </header>

                {/* <div className="flex-1 overflow-y-auto p-6 space-y-6"> */}
                <div className="flex-1 min-h-0 overflow-y-auto p-5 space-y-5 custom-scrollbar">
                    {/* Profile Name at the very top */}
                    <div className="space-y-1">
                        <label className="text-[10px] uppercase font-bold text-zinc-500 dark:text-zinc-400">Profile Name <span className="text-rose-500">*</span></label>
                        <input
                            ref={nameInputRef}
                            type="text"
                            autoComplete="off"
                            placeholder="e.g., sqlite_test"
                            value={form.profile_name}
                            onChange={(e) => {
                                const val = e.target.value.trim().replace(/[^a-zA-Z0-9_-]/g, "");
                                setForm({ ...form, profile_name: val, filepath: `~/.aiida/storage/${val}` });
                            }}
                            disabled={isSubmitting}
                            className="w-full bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-lg px-2.5 py-1.5 text-sm font-semibold focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all dark:text-zinc-200"
                        />
                    </div>

                    <div className="flex flex-col gap-3.5">
                        <div className="p-3 bg-zinc-50 dark:bg-zinc-900/30 rounded-xl border border-zinc-200 dark:border-zinc-800 space-y-3">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-1.5 text-zinc-500 dark:text-zinc-400">
                                    <User className="h-3.5 w-3.5" />
                                    <span className="text-[10px] font-bold uppercase tracking-wider">User Information</span>
                                </div>
                                {userInfoQuery.isLoading && <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-400" />}
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div className="space-y-1">
                                    <label className="text-[10px] uppercase font-bold text-zinc-400">First Name</label>
                                    <input
                                        value={form.first_name}
                                        onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                                        disabled={isSubmitting}
                                        className="w-full bg-white dark:bg-zinc-800 border border-zinc-200/50 dark:border-zinc-700/50 rounded-lg px-2.5 py-1.5 text-xs focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-900 outline-none transition-all dark:text-zinc-200"
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-[10px] uppercase font-bold text-zinc-400">Last Name</label>
                                    <input
                                        value={form.last_name}
                                        onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                                        disabled={isSubmitting}
                                        className="w-full bg-white dark:bg-zinc-800 border border-zinc-200/50 dark:border-zinc-700/50 rounded-lg px-2.5 py-1.5 text-xs focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-900 outline-none transition-all dark:text-zinc-200"
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-[10px] uppercase font-bold text-zinc-400 flex items-center gap-1"><Mail className="h-2.5 w-2.5" /> Email</label>
                                    <input
                                        type="email"
                                        value={form.email}
                                        onChange={(e) => setForm({ ...form, email: e.target.value })}
                                        disabled={isSubmitting}
                                        className="w-full bg-white dark:bg-zinc-800 border border-zinc-200/50 dark:border-zinc-700/50 rounded-lg px-2.5 py-1.5 text-xs focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-900 outline-none transition-all dark:text-zinc-200"
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-[10px] uppercase font-bold text-zinc-400">Institution</label>
                                    <input
                                        value={form.institution}
                                        onChange={(e) => setForm({ ...form, institution: e.target.value })}
                                        disabled={isSubmitting}
                                        className="w-full bg-white dark:bg-zinc-800 border border-zinc-200/50 dark:border-zinc-700/50 rounded-lg px-2.5 py-1.5 text-xs focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-900 outline-none transition-all dark:text-zinc-200"
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="space-y-1">
                            <label className="text-[10px] uppercase font-bold text-zinc-500 dark:text-zinc-400 flex items-center gap-1"><Database className="h-3 w-3" /> Backend Database</label>
                            <select
                                value={form.backend}
                                onChange={(e) => setForm({ ...form, backend: e.target.value })}
                                disabled={isSubmitting}
                                className="w-full h-8 bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-lg px-2 text-xs text-zinc-700 dark:text-zinc-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all"
                            >
                                <option value="core.sqlite_dos">sqlite_dos (Default)</option>
                                <option value="core.psql_dos">psql_dos</option>
                                <option value="core.sqlite_zip">sqlite_zip</option>
                            </select>
                        </div>

                        <div className="space-y-1 w-full">
                            <label className="text-[10px] uppercase font-bold text-zinc-500 dark:text-zinc-400 flex items-center gap-1"><FolderOpen className="h-3 w-3" /> Storage Filepath</label>
                            <input
                                value={form.filepath}
                                onChange={(e) => setForm({ ...form, filepath: e.target.value })}
                                disabled={isSubmitting}
                                placeholder="~/.aiida/storage/..."
                                className="w-full bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-lg px-2.5 py-1.5 text-xs font-mono text-zinc-600 dark:text-zinc-400 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all block"
                            />
                        </div>

                        <div className="flex flex-col gap-2 pt-2 border-t border-zinc-100 dark:border-zinc-800/60">
                            <label className="flex items-center gap-2 cursor-pointer group">
                                <button
                                    type="button"
                                    role="switch"
                                    aria-checked={form.set_as_default}
                                    onClick={() => setForm({ ...form, set_as_default: !form.set_as_default })}
                                    disabled={isSubmitting}
                                    className="relative shrink-0 w-8 h-4 bg-zinc-200 dark:bg-zinc-700 rounded-full transition-colors aria-checked:bg-blue-500"
                                >
                                    <span className={cn(
                                        "absolute top-0.5 left-0.5 w-3 h-3 bg-white rounded-full transition-transform",
                                        form.set_as_default ? "translate-x-4" : "translate-x-0"
                                    )} />
                                </button>
                                <span className="text-[11px] font-medium text-zinc-700 dark:text-zinc-300 group-hover:text-zinc-900 dark:group-hover:text-zinc-100 transition-colors">
                                    Switch to this profile after creation
                                </span>
                            </label>

                            <label className="flex items-center gap-2 cursor-pointer group opacity-80">
                                <button
                                    type="button"
                                    role="switch"
                                    aria-checked={rabbitmq}
                                    onClick={() => setRabbitmq(!rabbitmq)}
                                    disabled={isSubmitting}
                                    className="relative shrink-0 w-8 h-4 bg-zinc-200 dark:bg-zinc-700 rounded-full transition-colors aria-checked:bg-blue-500"
                                >
                                    <span className={cn(
                                        "absolute top-0.5 left-0.5 w-3 h-3 bg-white rounded-full transition-transform",
                                        rabbitmq ? "translate-x-4" : "translate-x-0"
                                    )} />
                                </button>
                                <div className="flex flex-col">
                                    <span className="text-[11px] font-medium text-zinc-700 dark:text-zinc-300 group-hover:text-zinc-900 dark:group-hover:text-zinc-100 transition-colors">
                                        Configure RabbitMQ
                                    </span>
                                    <span className="text-[9px] text-zinc-500 dark:text-zinc-400">Uses default AMQP localhost settings</span>
                                </div>
                            </label>
                        </div>
                    </div>

                    {error && (
                        <div className="p-3 bg-rose-50 dark:bg-rose-900/20 border border-rose-100 dark:border-rose-900/30 rounded-xl flex gap-x-2 text-rose-600 dark:text-rose-400 text-xs animate-in fade-in">
                            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                            {error}
                        </div>
                    )}
                </div>

                <footer className="flex-none px-6 py-4 border-t border-zinc-100 dark:border-zinc-900 bg-zinc-50/50 dark:bg-zinc-950/50 flex items-center justify-end gap-3">
                    <Button variant="ghost" size="sm" onClick={onClose} disabled={isSubmitting} className="h-8">Cancel</Button>
                    <Button
                        size="sm"
                        disabled={!form.profile_name || isSubmitting}
                        onClick={() => setupMutation.mutate(form)}
                        className="h-8 bg-blue-600 hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-700 text-white rounded-lg px-4 gap-1.5 text-xs"
                    >
                        {isSubmitting ? (
                            <>
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                Creating...
                            </>
                        ) : (
                            <>
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                Create
                            </>
                        )}
                    </Button>
                </footer>
            </aside>
        </>
    );

    return drawerContent;
}


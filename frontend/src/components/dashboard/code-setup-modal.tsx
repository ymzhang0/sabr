import { SetupCodePanel } from "@/components/dashboard/SetupCodePanel";

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
  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <SetupCodePanel
        computerLabel={computerLabel}
        onClose={onClose}
        onSuccess={onSuccess}
      />
    </div>
  );
}

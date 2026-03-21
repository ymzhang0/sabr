import type { SVGProps } from "react";

import { File, Folder, FolderOpen } from "lucide-react";

import { cn } from "@/lib/utils";

export type ExplorerIconNode = {
  name: string;
  type: "file" | "directory";
};

type ExplorerIconProps = SVGProps<SVGSVGElement> & {
  open?: boolean;
};

type LucideWrapperProps = {
  className?: string;
  open?: boolean;
};

export function FolderIcon({ open = false, className }: LucideWrapperProps) {
  const Icon = open ? FolderOpen : Folder;
  return <Icon className={cn("h-4 w-4 text-[#dcb67a]", className)} strokeWidth={1.9} />;
}

export function FileIcon({ className }: LucideWrapperProps) {
  return <File className={cn("h-4 w-4 text-[#c5c5c5]", className)} strokeWidth={1.9} />;
}

export function PythonIcon({ className, ...props }: ExplorerIconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={cn("h-4 w-4", className)}
      {...props}
    >
      <path
        d="M12.193 2.5c-4.79 0-4.488 2.077-4.488 2.077v2.152h4.57v.645H5.893S2.5 6.972 2.5 12.065c0 5.093 2.959 4.915 2.959 4.915h1.767v-2.481s-.095-2.959 2.904-2.959h5.017s2.818.046 2.818-2.724V4.77S18.395 2.5 12.193 2.5Z"
        fill="#3776AB"
      />
      <circle cx="9.014" cy="4.976" r="1.007" fill="#fff" />
      <path
        d="M11.807 21.5c4.79 0 4.488-2.077 4.488-2.077v-2.152h-4.57v-.645h6.382s3.393.402 3.393-4.691c0-5.093-2.959-4.915-2.959-4.915h-1.767v2.481s.095 2.959-2.904 2.959h-5.017s-2.818-.046-2.818 2.724v4.046S5.605 21.5 11.807 21.5Z"
        fill="#FFD43B"
      />
      <circle cx="14.986" cy="19.024" r="1.007" fill="#fff" />
    </svg>
  );
}

export function getExplorerNodeIcon(node: ExplorerIconNode, open = false) {
  if (node.type === "directory") {
    return <FolderIcon open={open} />;
  }

  if (node.name.toLowerCase().endsWith(".py")) {
    return <PythonIcon />;
  }

  return <FileIcon />;
}

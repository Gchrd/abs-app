"use client";

import Image from "next/image";
import { cn } from "@/lib/utils";

interface EyeToggleButtonProps {
  visible: boolean;
  onClick: () => void;
  className?: string;
  label?: string;
}

export function EyeToggleButton({ visible, onClick, className, label }: EyeToggleButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label ?? (visible ? "Hide password" : "Show password")}
      className={cn("shrink-0 opacity-60 hover:opacity-100 transition-opacity", className)}
    >
      <Image
        src={visible ? "/icons/eye-open.png" : "/icons/eye-closed.png"}
        alt=""
        width={18}
        height={18}
        className="dark:invert"
      />
    </button>
  );
}

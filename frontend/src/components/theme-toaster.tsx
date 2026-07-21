"use client";

import { useTheme } from "next-themes";
import { Toaster, type ToasterProps } from "sonner";

export function ThemeToaster(props: ToasterProps) {
  const { resolvedTheme } = useTheme();
  return <Toaster theme={(resolvedTheme as ToasterProps["theme"]) ?? "light"} {...props} />;
}

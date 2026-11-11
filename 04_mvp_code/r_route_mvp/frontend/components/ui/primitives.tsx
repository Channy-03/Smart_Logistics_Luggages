// shadcn/ui 패턴(cva + cn)으로 만든 최소 프리미티브. `npx shadcn add button card badge`로 교체 가능.
import { cva, type VariantProps } from "class-variance-authority";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import * as React from "react";

export const cn = (...c: ClassValue[]) => twMerge(clsx(c));

const button = cva(
  "inline-flex items-center justify-center gap-2 rounded-full text-sm font-semibold transition disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-light",
  {
    variants: {
      variant: {
        primary: "bg-brand text-white shadow-[0_6px_20px_-6px_rgba(16,185,129,.4)] hover:bg-[#0B8C60]",
        ghost: "border border-black/10 bg-white hover:bg-black/[.03]",
        dark: "bg-ink text-white hover:bg-black",
      },
      size: { sm: "h-8 px-3", md: "h-10 px-4", lg: "h-12 px-6 text-base" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);
export function Button({ className, variant, size, ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof button>) {
  return <button className={cn(button({ variant, size }), className)} {...p} />;
}

export function Card({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-[18px] border border-white/90 bg-white/70 p-5 shadow-glass backdrop-blur-xl", className)} {...p} />;
}

export function Badge({ className, tone = "mint", ...p }: React.HTMLAttributes<HTMLSpanElement> & { tone?: "mint" | "gray" | "amber" }) {
  const t = { mint: "bg-mint text-[#06694A]", gray: "bg-black/5 text-ink2", amber: "bg-[#FBEFD9] text-[#8A5605]" }[tone];
  return <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold", t, className)} {...p} />;
}

export function PageHead({ eyebrow, title, sub, right }: { eyebrow: string; title: string; sub?: string; right?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div>
        <div className="font-mono text-[11.5px] uppercase tracking-[.14em] text-brand">{eyebrow}</div>
        <h1 className="text-[28px] font-bold tracking-tight">{title}</h1>
        {sub && <p className="mt-1 max-w-[62ch] text-ink2">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

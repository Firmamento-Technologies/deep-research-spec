import type { FC, SVGProps } from 'react';

const Icon: FC<SVGProps<SVGSVGElement>> = ({ className, ...props }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={className} {...props}>
    <circle cx="12" cy="12" r="9" />
  </svg>
);

export const AlertCircle = Icon;
export const CheckCircle = Icon;
export const ChevronDown = Icon;
export const Download = Icon;
export const FileText = Icon;
export const Folder = Icon;
export const Lock = Icon;
export const LogOut = Icon;
export const Mail = Icon;
export const Plus = Icon;
export const Search = Icon;
export const Settings = Icon;
export const Shield = Icon;
export const Trash2 = Icon;
export const Upload = Icon;
export const User = Icon;
export const X = Icon;

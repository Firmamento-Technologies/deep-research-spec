import type { FC, SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement>;

const BaseIcon: FC<IconProps> = ({ className, children, ...props }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={className} {...props}>
    {children}
  </svg>
);

const circle = <circle cx="12" cy="12" r="9" />;

export const AlertCircle: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const CheckCircle: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const ChevronDown: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const Download: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const FileText: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const Folder: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const Lock: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const LogOut: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const Mail: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const Plus: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const Search: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const Settings: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const Shield: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const Trash2: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const Upload: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const User: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;
export const X: FC<IconProps> = (p) => <BaseIcon {...p}>{circle}</BaseIcon>;

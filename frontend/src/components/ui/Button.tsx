import type { ButtonHTMLAttributes, FC, PropsWithChildren } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  as?: 'button' | 'span';
}

const variantClass: Record<NonNullable<ButtonProps['variant']>, string> = {
  primary: 'bg-drs-accent hover:brightness-110 text-white',
  secondary: 'bg-drs-s2 hover:bg-drs-s3 text-drs-text border border-drs-border',
  danger: 'bg-drs-red hover:brightness-110 text-white',
  ghost: 'bg-transparent hover:bg-drs-s2 text-drs-muted hover:text-drs-text',
};

export const Button: FC<PropsWithChildren<ButtonProps>> = ({
  children,
  className = '',
  variant = 'primary',
  disabled,
  as = 'button',
  ...props
}) => {
  const Tag = as;

  return (
    <Tag
      {...props}
      {...(as === 'button' ? { disabled } : {})}
      className={`inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-drs-accent disabled:opacity-50 disabled:cursor-not-allowed ${variantClass[variant]} ${className}`}
    >
      {children}
    </Tag>
  );
};

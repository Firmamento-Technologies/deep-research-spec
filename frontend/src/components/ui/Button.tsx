import type { ButtonHTMLAttributes, FC, PropsWithChildren } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
}

const variantClass: Record<NonNullable<ButtonProps['variant']>, string> = {
  primary: 'bg-blue-600 hover:bg-blue-700 text-white',
  secondary: 'bg-gray-100 hover:bg-gray-200 text-gray-900 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-white',
  danger: 'bg-red-600 hover:bg-red-700 text-white',
};

export const Button: FC<PropsWithChildren<ButtonProps>> = ({
  children,
  className = '',
  variant = 'primary',
  disabled,
  ...props
}) => {
  return (
    <button
      {...props}
      disabled={disabled}
      className={`inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed ${variantClass[variant]} ${className}`}
    >
      {children}
    </button>
  );
};

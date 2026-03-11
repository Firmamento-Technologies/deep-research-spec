import type { FC, HTMLAttributes, PropsWithChildren } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {}

export const Card: FC<PropsWithChildren<CardProps>> = ({ children, className = '', ...props }) => {
  return (
    <div
      {...props}
      className={`rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800 ${className}`}
    >
      {children}
    </div>
  );
};

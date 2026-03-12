import type { FC, HTMLAttributes, PropsWithChildren } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {}

export const Card: FC<PropsWithChildren<CardProps>> = ({ children, className = '', ...props }) => {
  return (
    <div
      {...props}
      className={`rounded-card border border-drs-border bg-drs-s1 p-4 ${className}`}
    >
      {children}
    </div>
  );
};

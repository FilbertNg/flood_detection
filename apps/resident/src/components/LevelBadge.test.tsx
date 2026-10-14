import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { LevelBadge } from './LevelBadge';

describe('LevelBadge', () => {
  it('shows the level in English and Malay', () => {
    render(<LevelBadge level="warning" lang="en" />);
    expect(screen.getByText('Warning')).toBeInTheDocument();
    render(<LevelBadge level="danger" lang="ms" />);
    expect(screen.getByText('Bahaya')).toBeInTheDocument();
  });
});

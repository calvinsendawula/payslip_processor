import { Paper, Typography, Box, Divider, Button, Chip } from '@mui/material'
import { CheckCircle, Cancel, NavigateBefore, NavigateNext } from '@mui/icons-material'
import { useState } from 'react'

export function ResultsView({ data }) {
  const [currentPage, setCurrentPage] = useState(0)
  const pages = data.pages
  const totalPages = data.total_pages

  return (
    <Paper sx={{ p: 4 }}>
      <Typography variant="h5" gutterBottom sx={{ mb: 3 }}>
        Analysis Results {totalPages > 1 && `- Page ${pages[currentPage].page} of ${totalPages}`}
      </Typography>

      {totalPages > 1 && (
        <Box sx={{ mb: 3, display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<NavigateBefore />}
            onClick={() => setCurrentPage(p => Math.max(0, p - 1))}
            disabled={currentPage === 0}
          >
            Previous
          </Button>
          <Button
            variant="outlined"
            endIcon={<NavigateNext />}
            onClick={() => setCurrentPage(p => Math.min(pages.length - 1, p + 1))}
            disabled={currentPage === pages.length - 1}
          >
            Next
          </Button>
        </Box>
      )}

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <Section title="Employee Information" data={pages[currentPage].employee} />
        <Section title="Payment Information" data={pages[currentPage].payment} />
      </Box>
    </Paper>
  )
}

function Section({ title, data }) {
  return (
    <Box>
      <Typography variant="h6" gutterBottom sx={{ color: 'primary.main' }}>
        {title}
      </Typography>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {Object.entries(data).map(([key, value]) => (
          <Box key={key} sx={{ bgcolor: 'background.default', p: 2, borderRadius: 1 }}>
            <Typography variant="subtitle1" component="div" sx={{ fontWeight: 'bold', mb: 1 }}>
              {key.charAt(0).toUpperCase() + key.slice(1)}
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Typography variant="body1">
                Extracted: <strong>{value.extracted}</strong>
              </Typography>
              {value.stored && (
                <>
                  <Typography variant="body1">
                    Stored: <strong>{value.stored}</strong>
                  </Typography>
                  <Chip
                    icon={value.matches ? <CheckCircle /> : <Cancel />}
                    label={value.matches ? 'Match' : 'Mismatch'}
                    color={value.matches ? 'success' : 'error'}
                    variant="outlined"
                    size="small"
                  />
                </>
              )}
            </Box>
          </Box>
        ))}
      </Box>
    </Box>
  )
} 
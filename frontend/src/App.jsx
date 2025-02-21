import { useState } from 'react'
import { Container, Typography, Box, Paper, createTheme, ThemeProvider, CircularProgress } from '@mui/material'
import { FileUpload } from './components/FileUpload'
import { ResultsView } from './components/ResultsView'
import './App.css'

// Create a custom theme
const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    background: {
      default: '#f5f5f5',
    }
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
        },
      },
    },
  },
})

function App() {
  const [results, setResults] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  return (
    <ThemeProvider theme={theme}>
      <Box sx={{ 
        minHeight: '100vh',
        bgcolor: 'background.default',
        py: 4
      }}>
        <Container maxWidth="md">
          <Paper sx={{ p: 4, mb: 4 }}>
            <Typography 
              variant="h3" 
              component="h1" 
              gutterBottom
              sx={{ 
                fontWeight: 'bold',
                textAlign: 'center',
                color: 'primary.main',
                mb: 4
              }}
            >
              Payslip Processor
            </Typography>
            
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <FileUpload 
                onUploadComplete={setResults}
                setIsLoading={setIsLoading}
              />
              
              {isLoading && (
                <Box sx={{ 
                  display: 'flex', 
                  justifyContent: 'center',
                  alignItems: 'center',
                  gap: 2,
                  p: 4
                }}>
                  <CircularProgress />
                  <Typography variant="h6" color="text.secondary">
                    Processing your payslip...
                  </Typography>
                </Box>
              )}

              {results && !isLoading && (
                <ResultsView data={results} />
              )}
            </Box>
          </Paper>
        </Container>
      </Box>
    </ThemeProvider>
  )
}

export default App
